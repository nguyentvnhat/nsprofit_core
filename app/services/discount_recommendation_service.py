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


class DiscountAnalysisError(ValueError):
    """Predictable validation / empty-dataset failures for HTTP mapping."""


@dataclass(frozen=True)
class DiscountRunMeta:
    analysis_mode: str
    upload_id: int | None
    store_id: int | None
    source_summary: str
    date_range_used: dict[str, Any]
    warnings: tuple[str, ...]


def _primary_upload_id_from_orders(orders: list[Any]) -> int:
    uids = [int(o.upload_id) for o in orders if getattr(o, "upload_id", None) is not None]
    if not uids:
        return 0
    return max(set(uids), key=uids.count)


def _metrics_summary_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
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
    Returns the same top-level keys the FastAPI route has historically returned, plus additive meta.

    Precedence: ``store_id`` > new CSV upload > ``upload_id``.
    """
    warnings: list[str] = []
    mc = (merchant_code or "").strip()
    orders: list[Any] = []

    normalized_profit, profit_norm_warnings = normalize_profit_configuration(profit_configuration)
    warnings.extend(profit_norm_warnings)
    warnings.extend(list(normalized_profit.warnings))

    applied_cost_components: dict[str, Any] = {
        "cogs": False,
        "shipping_costs": False,
        "transaction_fees": False,
        "custom_costs": False,
        "notes": None,
    }

    if start_date is not None and end_date is not None and start_date > end_date:
        raise DiscountAnalysisError("start_date must be on or before end_date.")

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
        st = StoreRepository(session).get(int(store_id))
        if st is None:
            raise DiscountAnalysisError(f"store not found: {store_id}")
        resolved_store_id = int(st.id)
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
        primary_uid = _primary_upload_id_from_orders(orders)
        rows = build_discount_recommendation_rows_from_orders(orders)
        if not rows:
            raise DiscountAnalysisError(
                "no analyzable SKU line items for this store in the selected range."
            )
        rows, applied_cost_components = apply_profit_configuration_to_rows(orders, rows, normalized_profit)
        drafts = promotion_drafts_from_discount_rows(
            rows,
            upload_id=int(primary_uid),
            store_id=resolved_store_id,
            duration_days=int(duration_days),
            level=int(level),
            limit=int(limit),
        )
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
        if not filename or not str(filename).lower().endswith(".csv"):
            raise DiscountAnalysisError("file must be a .csv")
        if not file_bytes:
            raise DiscountAnalysisError("empty file")
        from app.repositories.merchant_repository import MerchantRepository

        merchant_id = None
        if mc:
            m = MerchantRepository(session).get_or_create_by_code(mc)
            merchant_id = int(m.id)
        resolved_upload_id = int(
            process_shopify_csv(
                session,
                file_bytes=file_bytes,
                filename=str(filename),
                merchant_id=merchant_id,
            )
        )
        orders = oar.load_orders_for_upload(
            resolved_upload_id,
            include_items=True,
            include_customer=False,
        )
        analysis_mode = "csv_upload"
        rows = build_discount_recommendation_rows_from_orders(orders)
        if not rows:
            up_err = UploadRepository(session).get(resolved_upload_id)
            raise DiscountAnalysisError(
                f"no analyzable line items for upload_id={resolved_upload_id} "
                f"(status={getattr(up_err, 'status', None)!r})."
            )
        rows, applied_cost_components = apply_profit_configuration_to_rows(orders, rows, normalized_profit)
        up_csv = UploadRepository(session).get(resolved_upload_id)
        csv_store_id = int(up_csv.store_id) if up_csv and getattr(up_csv, "store_id", None) else None
        drafts = promotion_drafts_from_discount_rows(
            rows,
            upload_id=resolved_upload_id,
            store_id=csv_store_id,
            duration_days=int(duration_days),
            level=int(level),
            limit=int(limit),
        )
        dashboard = get_dashboard_data(session, upload_id=resolved_upload_id)
        source_summary = f"csv_upload→upload_id={resolved_upload_id}"
        date_range_used = {"start_date": None, "end_date": None}

    elif upload_id is not None:
        resolved_upload_id = int(upload_id)
        up = UploadRepository(session).get(resolved_upload_id)
        if up is None:
            raise DiscountAnalysisError(f"upload not found: {resolved_upload_id}")
        orders = oar.load_orders_for_upload(resolved_upload_id, include_items=True, include_customer=False)
        if not orders:
            raise DiscountAnalysisError(
                f"no orders found for upload_id={resolved_upload_id}. "
                "Import may have failed or produced no normalized rows."
            )
        analysis_mode = "upload"
        rows = build_discount_recommendation_rows_from_orders(orders)
        if not rows:
            raise DiscountAnalysisError(
                f"no analyzable SKU line items for upload_id={resolved_upload_id}."
            )
        rows, applied_cost_components = apply_profit_configuration_to_rows(orders, rows, normalized_profit)
        upload_store_id = int(up.store_id) if getattr(up, "store_id", None) else None
        drafts = promotion_drafts_from_discount_rows(
            rows,
            upload_id=resolved_upload_id,
            store_id=upload_store_id,
            duration_days=int(duration_days),
            level=int(level),
            limit=int(limit),
        )
        dashboard = get_dashboard_data(session, upload_id=resolved_upload_id)
        source_summary = f"upload_id={resolved_upload_id}"
        date_range_used = {"start_date": None, "end_date": None}

    else:
        raise DiscountAnalysisError(
            "Provide one of: store_id, upload_id, or a CSV file (multipart field 'file')."
        )

    drafts_json = promotion_drafts_to_jsonable(drafts)
    guardrails = build_guardrails_from_upload_rows(rows, level=int(level), duration_days=int(duration_days))

    total = len(drafts)
    high_conf = sum(1 for d in drafts if str(getattr(d, "confidence", "") or "").lower().strip() == "high")
    heavy = sum(1 for d in drafts if float(getattr(d, "current_discount_pct", 0.0) or 0.0) >= 25.0)
    net_rev_total = sum(float(getattr(d, "net_revenue", 0.0) or 0.0) for d in drafts)

    mix: dict[str, int] = {"discount": 0, "bundle": 0, "flash_sale": 0}
    for d in drafts:
        ct = str(getattr(d, "campaign_type", "discount") or "discount")
        if ct in mix:
            mix[ct] += 1

    dashboard_json = dashboard_data_to_jsonable(dashboard)

    if orders:
        order_count = len(orders)
    elif resolved_upload_id is not None:
        order_count = len(oar.load_orders_for_upload(int(resolved_upload_id), limit=5000))
    else:
        order_count = 0

    # --- AI campaign log (best-effort) ---
    ds_id: int | None = None
    ss_id: int | None = None
    src_type: str | None = analysis_mode
    up_for_log = None
    if orders and getattr(orders[0], "upload_id", None):
        up_for_log = UploadRepository(session).get(int(orders[0].upload_id))
    elif resolved_upload_id is not None:
        up_for_log = UploadRepository(session).get(int(resolved_upload_id))
    if up_for_log is not None:
        ds_id = getattr(up_for_log, "data_source_id", None)
        ss_id = getattr(up_for_log, "sync_session_id", None)
        if resolved_store_id is None and getattr(up_for_log, "store_id", None):
            resolved_store_id = int(up_for_log.store_id)

    meta_run = DiscountRunMeta(
        analysis_mode=analysis_mode,
        upload_id=resolved_upload_id,
        store_id=resolved_store_id,
        source_summary=source_summary,
        date_range_used=date_range_used,
        warnings=tuple(warnings),
    )

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
