"""
Orchestration for /api/discount — keeps analytical layers explicit:

canonical orders → SKU line metrics → optional profit_configuration metrics (cost-aware bands)
→ discount heuristics → promotion drafts / guardrails → dashboard payload.

Signals and persisted insights remain upload-scoped in DB; store mode uses derived KPIs
from canonical orders only. Optional ``profit_configuration`` enriches SKU metrics before
heuristics; omitting it preserves legacy behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.repositories import OrderAnalysisRepository
from app.repositories.ai_campaign_log_repository import AiCampaignLogRepository
from app.repositories.store_repository import StoreRepository
from app.repositories.upload_repository import UploadRepository
from app.services.dashboard_service import (
    build_dashboard_data_from_canonical_orders,
    dashboard_data_to_jsonable,
    get_dashboard_data,
)
from app.services.discount_guardrails import build_guardrails_from_upload_rows
from app.services.discount_recommendation import build_discount_recommendation_rows_from_orders
from app.services.pipeline import process_shopify_csv
from app.services.profit_configuration_normalizer import normalize_profit_configuration, profit_configuration_to_jsonable
from app.services.profit_metrics import apply_profit_configuration_to_rows
from app.services.promotion_draft import promotion_drafts_from_discount_rows, promotion_drafts_to_jsonable
from app.services.recommendation_presenter import present_promotion_draft


class DiscountAnalysisError(ValueError):
    """Predictable validation / empty-dataset failures for HTTP mapping."""


@dataclass(frozen=True)
class DiscountRunMeta:
    """
    Immutable metadata describing one discount-analysis run.

    This helps keep execution context organized and makes the final API response
    easier to construct without mixing orchestration state everywhere in the function.
    """
    analysis_mode: str
    upload_id: int | None
    store_id: int | None
    source_summary: str
    date_range_used: dict[str, Any]
    warnings: tuple[str, ...]


def _primary_upload_id_from_orders(orders: list[Any]) -> int:
    """
    Infer the most representative upload_id from a list of canonical orders.

    Why this exists:
    - In store mode, orders may still carry upload_id references from earlier imports.
    - Some downstream draft-generation logic remains upload-aware.
    - We therefore choose the most common upload_id as the "primary" one.

    Returns:
    - 0 if no order has an upload_id
    - the most frequently occurring upload_id otherwise
    """
    uids = [int(o.upload_id) for o in orders if getattr(o, "upload_id", None) is not None]
    if not uids:
        return 0
    return max(set(uids), key=uids.count)


def _metrics_summary_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Build a compact summary of recommendation rows.

    This summary is used in:
    - API analysis output
    - AI campaign log payloads
    - quick trace/debug inspection

    Captures:
    - total SKU rows analyzed
    - total net revenue covered by those rows
    - high-confidence SKU count
    - count of rows enriched by profit_configuration
    """
    if not rows:
        return {
            "sku_count": 0,
            "total_net_revenue": 0.0,
            "high_confidence_skus": 0,
            "profit_configuration_applied_rows": 0,
        }
    high = sum(1 for r in rows if str(r.get("confidence") or "").lower().strip() == "high")
    net = sum(float(r.get("net_revenue") or 0.0) for r in rows)
    pc_rows = sum(
        1
        for r in rows
        if bool((r.get("metrics_profit") or {}).get("profit_configuration_applied"))
    )
    return {
        "sku_count": len(rows),
        "total_net_revenue": round(net, 2),
        "high_confidence_skus": int(high),
        "profit_configuration_applied_rows": int(pc_rows),
    }


def _traceability_block(
    *,
    rows: list[dict[str, Any]],
    order_count: int,
    analysis_mode: str,
    applied_cost_components: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Return a traceability descriptor for the current run.

    The goal is to make the analytical pipeline explicit to:
    - frontend consumers
    - logs
    - future debugging / audit work

    This block documents:
    - which pipeline layers were applied
    - how many orders / SKU rows were analyzed
    - whether optional cost components were used
    """
    return {
        "pipeline_layers": [
            "canonical_orders",
            "sku_line_metrics",
            "optional_profit_configuration_metrics",
            "discount_headroom_heuristic",
            "promotion_drafts",
        ],
        "note": (
            "Persisted metrics_engine signals and rule insights are upload-scoped; "
            "store mode exposes SKU metrics + derived dashboard KPIs only. "
            "Optional profit_configuration enriches SKU metrics before heuristics."
        ),
        "source": {
            "analysis_mode": analysis_mode,
            "canonical_order_count": int(order_count),
            "sku_row_count": len(rows),
        },
        "applied_cost_components": applied_cost_components or {},
    }


def run_discount_recommendation(
    session: Session,
    *,
    file_bytes: bytes | None,
    filename: str | None,
    merchant_code: str | None,
    upload_id: int | None,
    store_id: int | None,
    start_date: date | None,
    end_date: date | None,
    level: int,
    duration_days: int,
    limit: int,
    profit_configuration: Any | None = None,
) -> dict[str, Any]:
    """
    Run the full discount recommendation pipeline.

    Responsibilities
    ----------------
    1. Validate input combinations and precedence.
    2. Resolve the analysis source:
       - store_id
       - new CSV upload
       - existing upload_id
    3. Load canonical orders.
    4. Convert orders into SKU-level recommendation rows.
    5. Optionally enrich rows with profit_configuration.
    6. Generate promotion drafts and guardrails.
    7. Build dashboard payloads and analysis summaries.
    8. Persist a best-effort campaign log for traceability.

    Input precedence
    ----------------
    store_id > uploaded CSV file > upload_id

    Notes
    -----
    - store mode is the preferred path for long-term sync-ready analysis
    - CSV/upload flows are preserved for backward compatibility and demo workflows
    - profit_configuration is optional and should never break legacy behavior

    Returns
    -------
    A response payload that preserves the historical top-level structure while
    adding richer meta and traceability information.
    """
    warnings: list[str] = []
    mc = (merchant_code or "").strip()
    orders: list[Any] = []

    # Normalize optional profit configuration up front so every analysis mode
    # shares the same enrichment logic and warning collection behavior.
    normalized_profit, profit_norm_warnings = normalize_profit_configuration(profit_configuration)
    warnings.extend(profit_norm_warnings)
    warnings.extend(list(normalized_profit.warnings))

    # Track which cost components were actually applied during enrichment.
    # This is useful both for UI transparency and for campaign logging.
    applied_cost_components: dict[str, Any] = {
        "cogs": False,
        "shipping_costs": False,
        "transaction_fees": False,
        "custom_costs": False,
        "notes": None,
    }

    # Validate date range only when both boundaries exist.
    # Prevents silent execution of an invalid store-scoped range.
    if start_date is not None and end_date is not None and start_date > end_date:
        raise DiscountAnalysisError("start_date must be on or before end_date.")

    # store_id is the highest-precedence input. If it is provided alongside
    # another source, keep execution predictable by using store_id and adding warnings.
    if store_id is not None and file_bytes:
        warnings.append("store_id takes precedence; uploaded CSV was ignored.")
    if store_id is not None and upload_id is not None:
        warnings.append("store_id takes precedence over upload_id.")

    analysis_mode: str
    resolved_upload_id: int | None = None
    resolved_store_id: int | None = None
    orders: list[Any] = []
    oar = OrderAnalysisRepository(session)

    if store_id is not None:
        # --- Store mode ---
        # Analyze canonical orders already linked to a store.
        # This is the cleanest path for future sync-connected workflows.
        st = StoreRepository(session).get(int(store_id))
        if st is None:
            raise DiscountAnalysisError(f"store not found: {store_id}")
        resolved_store_id = int(st.id)

        # Load canonical orders for the store, optionally within the requested date range.
        orders = oar.load_orders_for_store(
            resolved_store_id,
            start_date=start_date,
            end_date=end_date,
            include_items=True,
            include_customer=False,
        )
        if not orders:
            raise DiscountAnalysisError(
                "no orders found for this store in the selected range. "
                "Ensure orders are linked to store_id or widen the date range."
            )

        analysis_mode = "store"

        # Some legacy/draft logic still benefits from an upload reference.
        # Use the most common upload_id found on the orders as a compatibility bridge.
        primary_uid = _primary_upload_id_from_orders(orders)

        # Convert canonical orders into SKU-level recommendation rows.
        # These rows are the bridge from raw order data to heuristic recommendations.
        rows = build_discount_recommendation_rows_from_orders(orders)
        if not rows:
            raise DiscountAnalysisError(
                "no analyzable SKU line items for this store in the selected range."
            )

        # Enrich SKU metrics with optional profit configuration before generating drafts.
        # This allows more profitability-aware recommendations without changing
        # the canonical order model itself.
        rows, applied_cost_components = apply_profit_configuration_to_rows(orders, rows, normalized_profit)

        # Generate promotion drafts, which represent the actionable recommendation layer.
        drafts = promotion_drafts_from_discount_rows(
            rows,
            upload_id=int(primary_uid),
            store_id=resolved_store_id,
            duration_days=int(duration_days),
            level=int(level),
            limit=int(limit),
        )

        # In store mode, dashboard metrics are derived directly from canonical orders
        # instead of relying on upload-scoped persisted metrics/signals.
        dashboard = build_dashboard_data_from_canonical_orders(
            session,
            orders,
            virtual_upload_id=0,
            file_name=f"store:{resolved_store_id}",
            status="ready",
        )

        dr = (start_date.isoformat() if start_date else None, end_date.isoformat() if end_date else None)
        source_summary = f"store_id={resolved_store_id}"
        date_range_used = {"start_date": dr[0], "end_date": dr[1]}

    elif file_bytes:
        # --- New CSV upload mode ---
        # Import a new Shopify CSV, normalize it into canonical data,
        # then run the same recommendation pipeline as other modes.
        if not filename or not str(filename).lower().endswith(".csv"):
            raise DiscountAnalysisError("file must be a .csv")
        if not file_bytes:
            raise DiscountAnalysisError("empty file")
        from app.repositories.merchant_repository import MerchantRepository

        merchant_id = None

        # Merchant code is optional. If provided, resolve or create the merchant
        # so the upload can be associated with business context.
        if mc:
            m = MerchantRepository(session).get_or_create_by_code(mc)
            merchant_id = int(m.id)

        # Process the CSV into the system and receive a persisted upload_id.
        resolved_upload_id = int(
            process_shopify_csv(
                session,
                file_bytes=file_bytes,
                filename=str(filename),
                merchant_id=merchant_id,
            )
        )

        # Reload canonical orders from the processed upload so downstream logic
        # works on normalized internal data rather than raw CSV content.
        orders = oar.load_orders_for_upload(
            resolved_upload_id,
            include_items=True,
            include_customer=False,
        )
        analysis_mode = "csv_upload"

        # Build SKU-level rows from normalized upload orders.
        rows = build_discount_recommendation_rows_from_orders(orders)
        if not rows:
            up_err = UploadRepository(session).get(resolved_upload_id)
            raise DiscountAnalysisError(
                f"no analyzable line items for upload_id={resolved_upload_id} "
                f"(status={getattr(up_err, 'status', None)!r})."
            )

        # Apply optional profit enrichment after order normalization and before heuristics.
        rows, applied_cost_components = apply_profit_configuration_to_rows(orders, rows, normalized_profit)

        # Try to carry through store context if the upload has already been linked to a store.
        up_csv = UploadRepository(session).get(resolved_upload_id)
        csv_store_id = int(up_csv.store_id) if up_csv and getattr(up_csv, "store_id", None) else None

        # Drafts represent the recommended promotion actions produced from the enriched rows.
        drafts = promotion_drafts_from_discount_rows(
            rows,
            upload_id=resolved_upload_id,
            store_id=csv_store_id,
            duration_days=int(duration_days),
            level=int(level),
            limit=int(limit),
        )

        # Reuse existing upload-based dashboard generation for backward compatibility.
        dashboard = get_dashboard_data(session, upload_id=resolved_upload_id)
        source_summary = f"csv_upload→upload_id={resolved_upload_id}"
        date_range_used = {"start_date": None, "end_date": None}

    elif upload_id is not None:
        # --- Existing upload mode ---
        # Re-run analysis on a previously stored upload without importing new data.
        resolved_upload_id = int(upload_id)
        up = UploadRepository(session).get(resolved_upload_id)
        if up is None:
            raise DiscountAnalysisError(f"upload not found: {resolved_upload_id}")

        # Load normalized orders associated with the historical upload.
        orders = oar.load_orders_for_upload(resolved_upload_id, include_items=True, include_customer=False)
        if not orders:
            raise DiscountAnalysisError(
                f"no orders found for upload_id={resolved_upload_id}. "
                "Import may have failed or produced no normalized rows."
            )

        analysis_mode = "upload"

        # Convert upload orders into SKU recommendation rows.
        rows = build_discount_recommendation_rows_from_orders(orders)
        if not rows:
            raise DiscountAnalysisError(
                f"no analyzable SKU line items for upload_id={resolved_upload_id}."
            )

        # Optionally enrich the rows with cost/profit configuration.
        rows, applied_cost_components = apply_profit_configuration_to_rows(orders, rows, normalized_profit)

        # Preserve store context when the upload is already linked to a store record.
        upload_store_id = int(up.store_id) if getattr(up, "store_id", None) else None

        # Generate promotion drafts from the enriched rows.
        drafts = promotion_drafts_from_discount_rows(
            rows,
            upload_id=resolved_upload_id,
            store_id=upload_store_id,
            duration_days=int(duration_days),
            level=int(level),
            limit=int(limit),
        )

        # Use the historical upload-based dashboard pipeline.
        dashboard = get_dashboard_data(session, upload_id=resolved_upload_id)
        source_summary = f"upload_id={resolved_upload_id}"
        date_range_used = {"start_date": None, "end_date": None}

    else:
        # No valid source was provided.
        raise DiscountAnalysisError(
            "Provide one of: store_id, upload_id, or a CSV file (multipart field 'file')."
        )

    # old
    # drafts_json = [present_promotion_draft(d) for d in drafts]

    # Present drafts in UI-friendly format, then enrich them with additional
    # compact display fields used by newer frontend experiences.
    drafts_json = [_enrich_presented_draft(present_promotion_draft(d)) for d in drafts]

    # Build guardrails from row-level analysis so the UI can explain recommendation
    # boundaries and cautionary constraints.
    guardrails = build_guardrails_from_upload_rows(rows, level=int(level), duration_days=int(duration_days))

    # Headline overview metrics used by summary cards and quick API inspection.
    total = len(drafts)
    high_conf = sum(1 for d in drafts if str(getattr(d, "confidence", "") or "").lower().strip() == "high")
    heavy = sum(1 for d in drafts if float(getattr(d, "current_discount_pct", 0.0) or 0.0) >= 25.0)
    net_rev_total = sum(float(getattr(d, "net_revenue", 0.0) or 0.0) for d in drafts)

    # Track the distribution of strategy types for quick overview rendering.
    mix: dict[str, int] = {"discount": 0, "bundle": 0, "flash_sale": 0}
    for d in drafts:
        ct = str(getattr(d, "campaign_type", "discount") or "discount")
        if ct in mix:
            mix[ct] += 1

    # Convert dashboard payload into a JSON-safe shape for response output.
    dashboard_json = dashboard_data_to_jsonable(dashboard)

    # Compute order_count for traceability and campaign logging.
    # Prefer already-loaded orders when available to avoid unnecessary reloads.
    if orders:
        order_count = len(orders)
    elif resolved_upload_id is not None:
        order_count = len(oar.load_orders_for_upload(int(resolved_upload_id), limit=5000))
    else:
        order_count = 0

    # --- AI campaign log (best-effort) ---
    # This log is for traceability and observability, not for driving the API result itself.
    ds_id: int | None = None
    ss_id: int | None = None
    src_type: str | None = analysis_mode
    up_for_log = None

    # Try to resolve upload-linked context from the first order when available.
    if orders and getattr(orders[0], "upload_id", None):
        up_for_log = UploadRepository(session).get(int(orders[0].upload_id))
    elif resolved_upload_id is not None:
        up_for_log = UploadRepository(session).get(int(resolved_upload_id))

    # Extract data source / sync context for downstream observability.
    if up_for_log is not None:
        ds_id = getattr(up_for_log, "data_source_id", None)
        ss_id = getattr(up_for_log, "sync_session_id", None)

        # Backfill store context when log-related upload metadata contains it.
        if resolved_store_id is None and getattr(up_for_log, "store_id", None):
            resolved_store_id = int(up_for_log.store_id)

    # Package core run metadata in one immutable object for cleaner downstream use.
    meta_run = DiscountRunMeta(
        analysis_mode=analysis_mode,
        upload_id=resolved_upload_id,
        store_id=resolved_store_id,
        source_summary=source_summary,
        date_range_used=date_range_used,
        warnings=tuple(warnings),
    )

    # Persist a best-effort campaign log entry so the system can later inspect:
    # - how the run was triggered
    # - what source/config was used
    # - what analytical context existed
    AiCampaignLogRepository(session).log_discount_api_run(
        analysis_mode=analysis_mode,
        upload_id=resolved_upload_id,
        store_id=resolved_store_id,
        source_type=src_type,
        data_source_id=ds_id,
        sync_session_id=ss_id,
        linked_order_count=int(order_count),
        decision_payload_json={
            "analysis_mode": analysis_mode,
            "upload_id": resolved_upload_id,
            "store_id": resolved_store_id,
            "config_completeness": normalized_profit.completeness,
            "applied_cost_components": applied_cost_components,
            "metrics_summary": _metrics_summary_from_rows(rows),
            "traceability": _traceability_block(
                rows=rows,
                order_count=int(order_count),
                analysis_mode=analysis_mode,
                applied_cost_components=applied_cost_components,
            ),
            "engine_level": int(level),
            "limit": int(limit),
        },
    )

    # old per
    # drafts_json = [present_promotion_draft(d) for d in drafts_json]

    # Return a stable response contract:
    # - meta: execution context, warnings, config info
    # - overview: top-level recommendation metrics
    # - guardrails: cautionary boundaries
    # - drafts: presented recommendation objects
    # - rows: underlying SKU analysis rows
    # - dashboard: broader KPI/dashboard payload
    # - analysis: traceability and deeper summary blocks
    return {
        "meta": {
            "engine_level": int(level),
            "duration_days": int(duration_days),
            "limit": int(limit),
            "filename": str(filename) if filename else None,
            "upload_id": resolved_upload_id,
            "store_id": resolved_store_id,
            "merchant_code": mc or None,
            "analysis_mode": meta_run.analysis_mode,
            "source_summary": meta_run.source_summary,
            "date_range_used": meta_run.date_range_used,
            "warnings": list(meta_run.warnings),
            "config_completeness": normalized_profit.completeness,
            "applied_cost_components": applied_cost_components,
            "profit_configuration": profit_configuration_to_jsonable(normalized_profit),
        },
        "overview": {
            "products_with_recs": int(total),
            "high_confidence_items": int(high_conf),
            "already_ge_25pct_off": int(heavy),
            "net_revenue_covered": float(round(net_rev_total, 2)),
            "strategy_mix": mix,
        },
        "guardrails": guardrails,
        "drafts": drafts_json,
        "rows": rows[: min(len(rows), int(limit))],
        "dashboard": dashboard_json,
        "analysis": {
            "metrics_summary": _metrics_summary_from_rows(rows),
            "signals_by_severity": dashboard_json.get("signals_by_severity", {}),
            "insights": dashboard_json.get("insights", []),
            "recommendations": {
                "draft_count": int(total),
                "row_count": len(rows),
            },
            "traceability": _traceability_block(
                rows=rows,
                order_count=int(order_count),
                analysis_mode=analysis_mode,
                applied_cost_components=applied_cost_components,
            ),
            "profit_configuration": profit_configuration_to_jsonable(normalized_profit),
        },
    }


def _safe_float(v: Any) -> float | None:
    """
    Safely coerce a value to float.

    Returns:
    - None for blank / invalid values
    - float for valid numeric-like values
    """
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _fmt_pct(v: Any) -> str | None:
    """
    Format a numeric percentage for UI display.

    Examples:
    - 5      -> "5%"
    - 5.5    -> "5.5%"
    - None   -> None
    """
    n = _safe_float(v)
    if n is None:
        return None
    if abs(n - round(n)) < 1e-9:
        return f"{int(round(n))}%"
    return f"{n:.1f}%"


def _fmt_money(v: Any) -> str | None:
    """
    Format a numeric value into a compact USD money string.

    Examples:
    - 12.5    -> "$12.50"
    - -1200   -> "-$1,200.00"
    - None    -> None
    """
    n = _safe_float(v)
    if n is None:
        return None
    sign = "-" if n < 0 else ""
    n = abs(n)
    return f"{sign}${n:,.2f}"


def _first_non_empty(*vals: Any) -> Any:
    """
    Return the first non-empty value from multiple candidates.

    Useful because presenter payloads may expose the same business value
    through multiple legacy or newer keys.
    """
    for v in vals:
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        return v
    return None


def _build_compact_recommendation_fields(draft: dict[str, Any]) -> dict[str, Any]:
    """
    Build compact UI-facing recommendation fields from a presented draft.

    Why this exists:
    - The same business signal may be available through multiple payload keys.
    - Frontend rendering benefits from a normalized, compact structure.
    - This helper adds display-friendly fields without forcing a hard payload rewrite.

    Produces:
    - compact_label
    - primary_numbers
    - money_view
    """
    current_pct = _first_non_empty(
        draft.get("current_discount_pct"),
        (draft.get("preview_discount_logic") or {}).get("current_discount_pct"),
    )
    recommended_pct = _first_non_empty(
        draft.get("recommended_discount_pct"),
        (draft.get("preview_discount_logic") or {}).get("recommended_discount_pct"),
    )
    duration_days = _first_non_empty(
        draft.get("duration_days"),
        draft.get("recommended_duration_days"),
        (draft.get("preview_discount_logic") or {}).get("duration_days"),
    )
    per_order = _first_non_empty(
        draft.get("estimated_margin_recovery_per_order"),
        draft.get("margin_recovery_per_order_usd"),
        (draft.get("expected_impact") or {}).get("margin_recovery_per_order_usd"),
        ((draft.get("ui_payload") or {}).get("primary_numbers") or {}).get("per_order_profit_impact"),
    )
    total_profit = _first_non_empty(
        draft.get("estimated_total_margin_recovery"),
        draft.get("total_margin_recovery_usd"),
        (draft.get("expected_impact") or {}).get("total_margin_recovery_usd"),
        ((draft.get("ui_payload") or {}).get("expected_impact") or {}).get("total_margin_recovery"),
    )
    revenue_mid = _first_non_empty(
        draft.get("revenue_recovery_mid"),
        ((draft.get("expected_impact") or {}).get("revenue_recovery") or {}).get("point_estimate_usd"),
    )

    # Preserve already formatted percentage strings when present;
    # otherwise, format numerics into stable UI strings.
    current_pct_s = current_pct if isinstance(current_pct, str) and "%" in current_pct else _fmt_pct(current_pct)
    recommended_pct_s = recommended_pct if isinstance(recommended_pct, str) and "%" in recommended_pct else _fmt_pct(recommended_pct)

    # Convert duration into a short compact display form such as "3d".
    duration_s = f"{int(float(duration_days))}d" if _safe_float(duration_days) is not None else None

    # Preserve already formatted money strings when present;
    # otherwise, convert numerics into USD display strings.
    per_order_s = per_order if isinstance(per_order, str) and "$" in per_order else _fmt_money(per_order)
    total_profit_s = total_profit if isinstance(total_profit, str) and "$" in total_profit else _fmt_money(total_profit)
    revenue_mid_s = revenue_mid if isinstance(revenue_mid, str) and "$" in revenue_mid else _fmt_money(revenue_mid)

    # Build one compact recommendation label suitable for cards, rows, or badges.
    compact_parts: list[str] = []
    if current_pct_s and recommended_pct_s:
        compact_parts.append(f"{current_pct_s} → {recommended_pct_s}")
    if duration_s:
        compact_parts.append(duration_s)
    if per_order_s:
        compact_parts.append(f"+{per_order_s.lstrip('-')}/order" if not per_order_s.startswith("-") else f"{per_order_s}/order")
    if total_profit_s:
        compact_parts.append(f"~{total_profit_s}")

    return {
        "compact_label": " · ".join(compact_parts) if compact_parts else None,
        "primary_numbers": {
            "discount_change": f"{current_pct_s} → {recommended_pct_s}" if current_pct_s and recommended_pct_s else None,
            "duration": f"{int(float(duration_days))} days" if _safe_float(duration_days) is not None else None,
            "per_order_profit_impact": (
                f"+{per_order_s.lstrip('-')} per order" if per_order_s and not per_order_s.startswith("-")
                else (f"{per_order_s} per order" if per_order_s else None)
            ),
            "total_profit_impact": f"~{total_profit_s} total" if total_profit_s else None,
            "revenue_midpoint": f"{revenue_mid_s} revenue midpoint" if revenue_mid_s else None,
        },
        "money_view": {
            "per_order_estimate": per_order_s,
            "total_profit_estimate": total_profit_s,
            "revenue_midpoint_estimate": revenue_mid_s,
        },
    }


def _enrich_presented_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """
    Add compact presentation fields into a presented draft.

    Important behavior:
    - this is additive enrichment only
    - existing non-empty UI fields are preserved
    - missing fields are backfilled from normalized compact values

    This keeps backward compatibility while improving frontend readability.
    """
    if not isinstance(draft, dict):
        return draft

    extra = _build_compact_recommendation_fields(draft)

    ui_payload = draft.get("ui_payload")
    if not isinstance(ui_payload, dict):
        ui_payload = {}

    primary_numbers = ui_payload.get("primary_numbers")
    if not isinstance(primary_numbers, dict):
        primary_numbers = {}

    # Only backfill values when the existing UI payload does not already provide them.
    for k, v in (extra.get("primary_numbers") or {}).items():
        if primary_numbers.get(k) in (None, "", []):
            primary_numbers[k] = v

    ui_payload["primary_numbers"] = primary_numbers

    # Backfill one compact recommendation summary string if the UI does not already have one.
    if ui_payload.get("recommendation_compact") in (None, "", []):
        ui_payload["recommendation_compact"] = extra.get("compact_label")

    draft["ui_payload"] = ui_payload

    # Mirror compact fields at top level for easier access by mixed/legacy consumers.
    if draft.get("compact_label") in (None, "", []):
        draft["compact_label"] = extra.get("compact_label")

    if draft.get("money_view") in (None, "", []):
        draft["money_view"] = extra.get("money_view")

    return draft