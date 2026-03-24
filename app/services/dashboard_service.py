"""Shared dashboard service for Streamlit pages."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import logging
import math
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.upload import Upload
from app.repositories import InsightRepository, OrderRepository, UploadRepository
from app.repositories.metric_repository import MetricRepository
from app.repositories.signal_repository import SignalRepository
from app.services.campaign_analyzer import (
    analyze_campaigns,
    campaign_summary_table_rows,
    top_campaign_risks,
)
from app.services.campaign_insight_enricher import (
    build_campaign_opportunity_summary,
    enrich_campaign_insights,
)
from app.services.campaign_extractor import parse_campaign_notes
from app.services.pipeline import process_shopify_csv

logger = logging.getLogger(__name__)


@dataclass
class DashboardData:
    upload_id: int
    file_name: str
    status: str
    kpis: dict[str, float]
    revenue_over_time: pd.DataFrame
    orders_over_time: pd.DataFrame
    orders_table: pd.DataFrame
    products_table: pd.DataFrame
    revenue_by_sku: pd.DataFrame
    top_3_sku_share: float
    top_3_line_revenue: float
    products_revenue_total: float
    customer_summary: dict[str, float]
    top_customers: pd.DataFrame
    signals_by_severity: dict[str, list[dict[str, Any]]]
    insights: list[dict[str, Any]]
    money_summary: dict[str, float | str]
    quick_wins: list[dict[str, Any]]
    loss_drivers: list[dict[str, Any]]
    campaign_results: list[dict[str, Any]]
    campaign_summary_table: list[dict[str, Any]]
    top_campaign_risks: list[dict[str, Any]]
    top_campaign_insights: list[dict[str, Any]]
    enriched_campaign_insights: list[dict[str, Any]]
    campaign_opportunity_summary: dict[str, Any]


def _latest_upload_id(session: Session) -> int | None:
    uid = session.scalars(select(Upload.id).order_by(Upload.id.desc()).limit(1)).first()
    return int(uid) if uid is not None else None


def list_uploads(session: Session, limit: int = 50) -> list[dict[str, Any]]:
    stmt = select(Upload).order_by(Upload.id.desc()).limit(limit)
    ups = session.scalars(stmt).all()
    return [
        {"id": u.id, "file_name": u.file_name, "status": u.status, "row_count": u.row_count}
        for u in ups
    ]


def run_dashboard_pipeline(
    session: Session,
    *,
    file_bytes: bytes,
    filename: str,
) -> DashboardData:
    """Run full pipeline and return page-ready dashboard data."""
    upload_id = process_shopify_csv(session, file_bytes=file_bytes, filename=filename)
    return get_dashboard_data(session, upload_id=upload_id)


def get_dashboard_data(session: Session, upload_id: int | None = None) -> DashboardData:
    uid = upload_id or _latest_upload_id(session)
    if uid is None:
        raise ValueError("No processed upload found.")
    upload = UploadRepository(session).get(uid)
    if upload is None:
        raise ValueError(f"Upload not found: {uid}")

    metrics_map = _load_metric_snapshots(session, uid)
    orders_df = _build_orders_table(session, uid)
    revenue_over_time, orders_over_time = _build_time_series(orders_df)
    products_table, revenue_by_sku, top_3_sku_share, top_3_line_revenue, products_revenue_total = _build_products(
        session, uid
    )
    customer_summary, top_customers = _build_customers(orders_df)
    signals_by_severity = _build_signals(session, uid)
    money_summary = _build_money_summary(metrics_map, orders_df)
    loss_drivers = _build_loss_drivers(money_summary)
    insights = _build_insights(
        session,
        uid,
        money_summary=money_summary,
        signals_by_severity=signals_by_severity,
    )
    quick_wins = _build_quick_wins(insights, signals_by_severity, money_summary)

    campaign_results: list[dict[str, Any]] = []
    campaign_summary_table: list[dict[str, Any]] = []
    top_c_risks: list[dict[str, Any]] = []
    top_c_insights: list[dict[str, Any]] = []
    enriched_campaign_insights: list[dict[str, Any]] = []
    campaign_opportunity_summary: dict[str, Any] = {}
    try:
        ods, its, custs = _load_upload_dataset_for_campaigns(session, uid)
        if ods:
            campaign_results = analyze_campaigns(ods, its, custs)
            campaign_summary_table = campaign_summary_table_rows(campaign_results)
            top_c_risks = top_campaign_risks(campaign_results)
            enriched_campaign_insights = enrich_campaign_insights(campaign_results)
            campaign_opportunity_summary = build_campaign_opportunity_summary(enriched_campaign_insights)
            top_c_insights = enriched_campaign_insights[:10]
    except Exception as exc:  # noqa: BLE001 — optional dimension layer must not break dashboard
        logger.warning("Campaign analysis skipped for upload_id=%s: %s", uid, exc)

    logger.debug(
        "Dashboard payload built upload_id=%s metrics=%s signals(high/med/low)=(%s/%s/%s) insights=%s",
        uid,
        len(metrics_map),
        len(signals_by_severity.get("high", [])),
        len(signals_by_severity.get("medium", [])),
        len(signals_by_severity.get("low", [])),
        len(insights),
    )

    fallback_kpis = _kpis_from_orders(orders_df)
    kpis = {
        "total_revenue": metrics_map.get("gross_revenue", fallback_kpis["total_revenue"]),
        "net_revenue": metrics_map.get("net_revenue", fallback_kpis["net_revenue"]),
        "aov": metrics_map.get("aov", fallback_kpis["aov"]),
        "total_orders": metrics_map.get("total_orders", fallback_kpis["total_orders"]),
        "discount_rate": float(money_summary.get("discount_as_pct_revenue", 0.0) or 0.0),
        "refund_rate": float(money_summary.get("refund_as_pct_revenue", 0.0) or 0.0),
        "estimated_leakage_pct": float(money_summary.get("estimated_revenue_leakage_pct", 0.0) or 0.0),
        "estimated_post_discount_and_shipping_revenue": float(
            money_summary.get("estimated_post_discount_and_shipping_revenue", 0.0) or 0.0
        ),
    }

    return DashboardData(
        upload_id=uid,
        file_name=upload.file_name,
        status=upload.status,
        kpis=kpis,
        revenue_over_time=revenue_over_time,
        orders_over_time=orders_over_time,
        orders_table=orders_df,
        products_table=products_table,
        revenue_by_sku=revenue_by_sku,
        top_3_sku_share=top_3_sku_share,
        top_3_line_revenue=top_3_line_revenue,
        products_revenue_total=products_revenue_total,
        customer_summary=customer_summary,
        top_customers=top_customers,
        signals_by_severity=signals_by_severity,
        insights=insights,
        money_summary=money_summary,
        quick_wins=quick_wins,
        loss_drivers=loss_drivers,
        campaign_results=campaign_results,
        campaign_summary_table=campaign_summary_table,
        top_campaign_risks=top_c_risks,
        top_campaign_insights=top_c_insights,
        enriched_campaign_insights=enriched_campaign_insights,
        campaign_opportunity_summary=campaign_opportunity_summary,
    )


def _load_metric_snapshots(session: Session, upload_id: int) -> dict[str, float]:
    rows = MetricRepository(session).list_for_upload(upload_id)
    out: dict[str, float] = {}
    for s in rows:
        # New pipeline stores per-domain scopes (revenue/orders/products/customers),
        # not only "overall". Accept all all-time scalar snapshots.
        if s.period_type == "all_time" and s.dimension_1 is None and s.dimension_2 is None:
            out[s.metric_code] = float(s.metric_value)
    return out


def _load_upload_dataset_for_campaigns(
    session: Session, upload_id: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Rebuild normalized-shape dicts (orders, line items, customers) for in-memory campaign slicing.

    Aligns with :func:`normalize_shopify_data` / metrics engine expectations (Decimals on money fields).
    """
    orders = OrderRepository(session).list_orders_for_upload(
        upload_id,
        include_items=True,
        include_customer=True,
        limit=5000,
    )
    order_dicts: list[dict[str, Any]] = []
    item_dicts: list[dict[str, Any]] = []
    customers_map: dict[str, dict[str, Any]] = {}

    for o in orders:
        camp = parse_campaign_notes(o.notes)
        od: dict[str, Any] = {
            "order_name": o.order_name,
            "external_order_id": o.external_order_id,
            "order_date": o.order_date,
            "currency": o.currency,
            "financial_status": o.financial_status,
            "fulfillment_status": o.fulfillment_status,
            "source_name": o.source_name,
            "shipping_country": o.shipping_country,
            "subtotal_price": o.subtotal_price,
            "discount_amount": o.discount_amount,
            "shipping_amount": o.shipping_amount,
            "tax_amount": o.tax_amount,
            "refunded_amount": o.refunded_amount,
            "total_price": o.total_price,
            "net_revenue": o.net_revenue,
            "total_quantity": o.total_quantity,
            "is_cancelled": o.is_cancelled,
            "is_repeat_customer": o.is_repeat_customer,
            "customer_email": o.customer.email if o.customer else None,
        }
        od.update(camp)
        order_dicts.append(od)

        if o.customer and o.customer.email:
            ce = str(o.customer.email).strip()
            if ce and ce not in customers_map:
                fn = o.customer.first_name or ""
                ln = o.customer.last_name or ""
                disp = " ".join(p for p in (fn, ln) if p).strip() or None
                customers_map[ce] = {
                    "email": ce,
                    "name": disp,
                    "shopify_customer_id": o.customer.external_id,
                }

        for it in o.items or []:
            item_dicts.append(
                {
                    "order_name": o.order_name,
                    "sku": it.sku,
                    "product_name": it.product_name,
                    "variant_name": it.variant_name,
                    "vendor": it.vendor,
                    "quantity": it.quantity,
                    "unit_price": it.unit_price,
                    "line_discount_amount": it.line_discount_amount,
                    "line_total": it.line_total,
                    "net_line_revenue": it.net_line_revenue,
                    "requires_shipping": it.requires_shipping,
                }
            )

    return order_dicts, item_dicts, list(customers_map.values())


def _build_orders_table(session: Session, upload_id: int) -> pd.DataFrame:
    # Orders table is order-level only, keep it fast by avoiding line-item joins.
    orders = OrderRepository(session).list_orders_for_upload(
        upload_id,
        include_items=False,
        include_customer=True,
        limit=5000,
    )
    rows: list[dict[str, Any]] = []
    for o in orders:
        rows.append(
            {
                "order_name": o.order_name,
                "order_date": o.order_date,
                "country": o.shipping_country,
                "status": o.financial_status,
                "fulfillment_status": o.fulfillment_status,
                "customer_email": o.customer.email if o.customer else None,
                "total_revenue": float(o.total_price or 0),
                "net_revenue": float(o.net_revenue or 0),
                "discount": float(o.discount_amount or 0),
                "quantity": int(o.total_quantity or 0),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    return df


def _kpis_from_orders(orders_df: pd.DataFrame) -> dict[str, float]:
    if orders_df.empty:
        return {
            "total_revenue": 0.0,
            "net_revenue": 0.0,
            "aov": 0.0,
            "total_orders": 0.0,
        }
    total_revenue = float(orders_df["total_revenue"].sum())
    net_revenue = float(orders_df["net_revenue"].sum())
    total_orders = float(len(orders_df))
    aov = (net_revenue / total_orders) if total_orders > 0 else 0.0
    return {
        "total_revenue": total_revenue,
        "net_revenue": net_revenue,
        "aov": aov,
        "total_orders": total_orders,
    }


def _fmt_money(value: float | int | None) -> str:
    try:
        v = float(value or 0.0)
    except Exception:
        v = 0.0
    if not math.isfinite(v):
        v = 0.0
    return f"${v:,.2f} USD"


def _fmt_money_markdown(value: float | int | None) -> str:
    """Currency string safe inside Streamlit ``st.markdown`` (``$`` would start LaTeX math)."""
    return _fmt_money(value).replace("$", r"\$")


def _safe_pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def _build_money_summary(metrics_map: dict[str, float], orders_df: pd.DataFrame) -> dict[str, float | str]:
    gross_revenue = float(metrics_map.get("gross_revenue", 0.0) or 0.0)
    if gross_revenue <= 0 and not orders_df.empty and "total_revenue" in orders_df.columns:
        gross_revenue = float(orders_df["total_revenue"].sum())

    discount_amount_total = float(metrics_map.get("discount_amount_total", metrics_map.get("total_discounts", 0.0)) or 0.0)
    if discount_amount_total <= 0 and not orders_df.empty and "discount" in orders_df.columns:
        discount_amount_total = float(orders_df["discount"].sum())

    shipping_amount_total = float(metrics_map.get("total_shipping", 0.0) or 0.0)
    refunded_amount_total = float(metrics_map.get("total_refunds", 0.0) or 0.0)

    discount_as_pct_revenue = _safe_pct(discount_amount_total, gross_revenue)
    shipping_as_pct_revenue = _safe_pct(shipping_amount_total, gross_revenue)
    refund_as_pct_revenue = _safe_pct(refunded_amount_total, gross_revenue)

    estimated_post_discount_revenue = gross_revenue - discount_amount_total
    estimated_post_discount_and_shipping_revenue = gross_revenue - discount_amount_total - shipping_amount_total
    estimated_revenue_leakage_total = discount_amount_total + shipping_amount_total + refunded_amount_total
    estimated_revenue_leakage_pct = _safe_pct(estimated_revenue_leakage_total, gross_revenue)

    return {
        "gross_revenue": gross_revenue,
        "discount_amount_total": discount_amount_total,
        "shipping_amount_total": shipping_amount_total,
        "refunded_amount_total": refunded_amount_total,
        "discount_as_pct_revenue": discount_as_pct_revenue,
        "shipping_as_pct_revenue": shipping_as_pct_revenue,
        "refund_as_pct_revenue": refund_as_pct_revenue,
        "estimated_post_discount_revenue": estimated_post_discount_revenue,
        "estimated_post_discount_and_shipping_revenue": estimated_post_discount_and_shipping_revenue,
        "estimated_revenue_leakage_total": estimated_revenue_leakage_total,
        "estimated_revenue_leakage_pct": estimated_revenue_leakage_pct,
    }


def _build_loss_drivers(money_summary: dict[str, float | str]) -> list[dict[str, Any]]:
    discount_total = float(money_summary.get("discount_amount_total", 0.0) or 0.0)
    shipping_total = float(money_summary.get("shipping_amount_total", 0.0) or 0.0)
    refund_total = float(money_summary.get("refunded_amount_total", 0.0) or 0.0)
    return [
        {
            "driver_code": "discount",
            "label": "Discounts",
            "amount": discount_total,
            "pct_revenue": float(money_summary.get("discount_as_pct_revenue", 0.0) or 0.0),
            "description": "Revenue given up through promotions and markdown mechanics.",
        },
        {
            "driver_code": "shipping",
            "label": "Shipping",
            "amount": shipping_total,
            "pct_revenue": float(money_summary.get("shipping_as_pct_revenue", 0.0) or 0.0),
            "description": "Shipping spend that reduces retained revenue capacity.",
        },
        {
            "driver_code": "refunds",
            "label": "Refunds",
            "amount": refund_total,
            "pct_revenue": float(money_summary.get("refund_as_pct_revenue", 0.0) or 0.0),
            "description": "Revenue reversed after purchase due to refunds/returns.",
        },
    ]


def _build_time_series(orders_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if orders_df.empty or "order_date" not in orders_df.columns:
        return pd.DataFrame(columns=["revenue"]), pd.DataFrame(columns=["orders"])

    ts = orders_df.dropna(subset=["order_date"]).copy()
    if ts.empty:
        return pd.DataFrame(columns=["revenue"]), pd.DataFrame(columns=["orders"])

    ts["day"] = ts["order_date"].dt.date
    revenue = ts.groupby("day", as_index=True)["net_revenue"].sum().to_frame("revenue")
    order_count = ts.groupby("day", as_index=True)["order_name"].count().to_frame("orders")
    return revenue.sort_index(), order_count.sort_index()


def _build_products(
    session: Session, upload_id: int
) -> tuple[pd.DataFrame, pd.DataFrame, float, float, float]:
    # Products breakdown needs line items.
    orders = OrderRepository(session).list_orders_for_upload(
        upload_id,
        include_items=True,
        include_customer=False,
    )
    rows: list[dict[str, Any]] = []
    for o in orders:
        for li in o.items:
            rows.append(
                {
                    "sku": li.sku or "UNKNOWN",
                    "product_name": li.product_name,
                    "quantity": int(li.quantity or 0),
                    "revenue": float(li.net_line_revenue or li.line_total or 0),
                }
            )

    if not rows:
        empty = pd.DataFrame(columns=["sku", "product_name", "quantity", "revenue"])
        return empty, pd.DataFrame(columns=["revenue"]), 0.0, 0.0, 0.0

    df = pd.DataFrame(rows)
    grouped = (
        df.groupby(["sku", "product_name"], dropna=False, as_index=False)
        .agg(quantity=("quantity", "sum"), revenue=("revenue", "sum"))
        .sort_values("revenue", ascending=False)
    )
    revenue_by_sku = grouped.groupby("sku", as_index=True)["revenue"].sum().to_frame("revenue")
    total_revenue = float(grouped["revenue"].sum())
    top3_revenue = float(grouped.head(3)["revenue"].sum())
    top3_share = (top3_revenue / total_revenue) if total_revenue > 0 else 0.0
    return grouped, revenue_by_sku, top3_share, top3_revenue, total_revenue


def _build_customers(orders_df: pd.DataFrame) -> tuple[dict[str, float], pd.DataFrame]:
    if orders_df.empty:
        return {
            "new_customers": 0.0,
            "repeat_customers": 0.0,
            "new_aov": 0.0,
            "repeat_aov": 0.0,
        }, pd.DataFrame(columns=["customer_email", "orders", "net_revenue", "aov"])

    cdf = orders_df.copy()
    cdf["customer_email"] = cdf["customer_email"].fillna("guest")

    by_customer = (
        cdf.groupby("customer_email", as_index=False)
        .agg(orders=("order_name", "count"), net_revenue=("net_revenue", "sum"))
        .sort_values("net_revenue", ascending=False)
    )
    by_customer["aov"] = by_customer["net_revenue"] / by_customer["orders"].clip(lower=1)

    new_mask = by_customer["orders"] <= 1
    repeat_mask = by_customer["orders"] > 1

    summary = {
        "new_customers": float(new_mask.sum()),
        "repeat_customers": float(repeat_mask.sum()),
        "new_aov": float(by_customer.loc[new_mask, "aov"].mean() or 0.0),
        "repeat_aov": float(by_customer.loc[repeat_mask, "aov"].mean() or 0.0),
    }
    return summary, by_customer.head(25)


def _map_severity(raw: str) -> str:
    sev = (raw or "").strip().lower()
    if sev in {"critical", "error", "warning", "high"}:
        return "high"
    if sev in {"medium", "moderate"}:
        return "medium"
    return "low"


def _build_signals(session: Session, upload_id: int) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows = SignalRepository(session).list_for_upload(upload_id)
    for s in rows:
        level = _map_severity(s.severity)
        grouped[level].append(
            {
                "signal_code": s.signal_code,
                "severity": s.severity,
                "entity_type": s.entity_type,
                "entity_key": s.entity_key,
                "signal_value": float(s.signal_value or 0),
                "threshold_value": float(s.threshold_value or 0),
                "context": s.signal_context_json or {},
            }
        )
    for level in ("high", "medium", "low"):
        grouped.setdefault(level, [])
    return dict(grouped)


def _build_insights(
    session: Session,
    upload_id: int,
    *,
    money_summary: dict[str, float | str],
    signals_by_severity: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    def normalize_priority(raw: str | None) -> str:
        p = (raw or "").strip().lower()
        if p == "high":
            return "high"
        if p in {"medium", "normal"}:
            return "medium"
        return "low"

    rows = InsightRepository(session).list_for_upload(upload_id)
    base = [
        {
            "insight_code": i.insight_code,
            "category": i.category,
            "priority": normalize_priority(i.priority),
            "title": i.title,
            "summary": i.summary,
            "implication": i.implication_text,
            "action": i.recommended_action,
        }
        for i in rows
    ]
    return [_enrich_insight_money_framing(x, money_summary, signals_by_severity) for x in base]


def _insight_text_blob(insight: dict[str, Any]) -> str:
    """Lowercased concat of fields used to detect discount/shipping/refund-related narratives."""
    parts = (
        insight.get("insight_code"),
        insight.get("category"),
        insight.get("title"),
        insight.get("summary"),
        insight.get("implication"),
    )
    return " ".join(str(p or "") for p in parts).lower()


def _enrich_insight_money_framing(
    insight: dict[str, Any],
    money_summary: dict[str, float | str],
    signals_by_severity: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    out = dict(insight)
    blob = _insight_text_blob(out)

    discount_pct = float(money_summary.get("discount_as_pct_revenue", 0.0) or 0.0) * 100.0
    shipping_pct = float(money_summary.get("shipping_as_pct_revenue", 0.0) or 0.0) * 100.0
    refund_pct = float(money_summary.get("refund_as_pct_revenue", 0.0) or 0.0) * 100.0
    leakage_pct = float(money_summary.get("estimated_revenue_leakage_pct", 0.0) or 0.0) * 100.0
    discount_amt = float(money_summary.get("discount_amount_total", 0.0) or 0.0)
    shipping_amt = float(money_summary.get("shipping_amount_total", 0.0) or 0.0)
    refund_amt = float(money_summary.get("refunded_amount_total", 0.0) or 0.0)
    leakage_amt = float(money_summary.get("estimated_revenue_leakage_total", 0.0) or 0.0)
    gross_rev = float(money_summary.get("gross_revenue", 0.0) or 0.0)

    if discount_amt <= 0 and discount_pct > 0 and gross_rev > 0:
        discount_amt = gross_rev * (discount_pct / 100.0)
    if shipping_amt <= 0 and shipping_pct > 0 and gross_rev > 0:
        shipping_amt = gross_rev * (shipping_pct / 100.0)
    if refund_amt <= 0 and refund_pct > 0 and gross_rev > 0:
        refund_amt = gross_rev * (refund_pct / 100.0)

    high_codes = {str(s.get("signal_code", "")) for s in signals_by_severity.get("high", [])}
    medium_codes = {str(s.get("signal_code", "")) for s in signals_by_severity.get("medium", [])}

    money_impact = ""
    trade_off = ""
    confidence = "low"

    if "refund" in blob:
        money_impact = (
            f"Refunds account for approximately {_fmt_money_markdown(refund_amt)} "
            f"({refund_pct:.1f}% of gross revenue)."
        )
        trade_off = "Tightening return controls can reduce leakage but may impact customer trust."
        confidence = "high" if "ELEVATED_REFUND_RATE" in high_codes else "medium"
    elif "shipping" in blob:
        money_impact = (
            f"Shipping accounts for approximately {_fmt_money_markdown(shipping_amt)} "
            f"({shipping_pct:.1f}% of gross revenue)."
        )
        trade_off = "Raising free-shipping thresholds can lift AOV but may reduce completion for price-sensitive buyers."
        confidence = "high" if "FREE_SHIPPING_OPPORTUNITY" in medium_codes else "medium"
    elif "discount" in blob or "markdown" in blob:
        money_impact = (
            f"Discounts account for approximately {_fmt_money_markdown(discount_amt)} "
            f"({discount_pct:.1f}% of gross revenue)."
        )
        trade_off = "Reducing discounts too aggressively may weaken short-term conversion."
        confidence = (
            "high"
            if ("HIGH_DISCOUNT_DEPENDENCY_V2" in high_codes or "HIGH_DISCOUNT_DEPENDENCY" in high_codes)
            else "medium"
        )
    elif "concentration" in blob:
        money_impact = "Revenue is concentrated in a narrow set of drivers, which increases downside volatility risk."
        trade_off = "Pushing current winners can improve short-term efficiency but increases concentration exposure."
        confidence = "high" if ("SOURCE_CONCENTRATION_RISK" in high_codes or "HERO_SKU_CONCENTRATION" in high_codes) else "medium"
    elif "aov" in blob or "basket" in blob or "bundle" in blob:
        money_impact = "A significant share of demand appears to come from lower-value baskets, suggesting AOV headroom."
        trade_off = "Aggressive basket-size tactics can increase friction if not aligned with customer intent."
        confidence = "medium"
    elif leakage_pct > 0:
        money_impact = (
            f"Estimated revenue leakage from discounts, shipping, and refunds is approximately "
            f"{_fmt_money_markdown(leakage_amt)} ({leakage_pct:.1f}% of gross revenue)."
        )
        trade_off = "Reducing leakage improves retention of revenue but may require conversion-risk trade-offs."
        confidence = "medium"

    out["money_impact"] = money_impact
    out["trade_off"] = trade_off
    out["confidence"] = confidence
    return out


def _build_quick_wins(
    insights: list[dict[str, Any]],
    signals_by_severity: dict[str, list[dict[str, Any]]],
    money_summary: dict[str, float | str],
) -> list[dict[str, Any]]:
    high_codes = {str(s.get("signal_code", "")) for s in signals_by_severity.get("high", [])}
    medium_codes = {str(s.get("signal_code", "")) for s in signals_by_severity.get("medium", [])}
    all_codes = high_codes | medium_codes | {str(s.get("signal_code", "")) for s in signals_by_severity.get("low", [])}

    out: list[dict[str, Any]] = []
    seen_titles: set[str] = set()

    def add(title: str, rationale: str, impact_type: str, priority: str) -> None:
        if title in seen_titles:
            return
        seen_titles.add(title)
        out.append(
            {
                "title": title,
                "rationale": rationale,
                "impact_type": impact_type,
                "priority": priority,
            }
        )

    discount_pct = float(money_summary.get("discount_as_pct_revenue", 0.0) or 0.0)
    if "HIGH_DISCOUNT_DEPENDENCY_V2" in all_codes or discount_pct > 0.10:
        add(
            "Reduce discount dependency",
            "Discount share of revenue is elevated and may be compressing retained value.",
            "leakage_reduction",
            "high",
        )
    if "FREE_SHIPPING_OPPORTUNITY" in all_codes:
        add(
            "Tune free-shipping threshold",
            "Orders clustering below threshold suggest immediate basket-size upside.",
            "revenue_opportunity",
            "medium",
        )
    if "BUNDLE_OPPORTUNITY" in all_codes:
        add(
            "Promote top bundle pairs",
            "Frequent co-purchase patterns indicate a fast AOV lift opportunity.",
            "revenue_opportunity",
            "medium",
        )
    if "DATA_HYGIENE_ISSUE" in all_codes:
        add(
            "Fix blank SKU tracking",
            "Missing SKU revenue reduces decision quality in merchandising and inventory.",
            "risk_reduction",
            "medium",
        )
    if "SOURCE_CONCENTRATION_RISK" in all_codes or "HERO_SKU_CONCENTRATION" in all_codes:
        add(
            "Reduce concentration exposure",
            "Revenue concentration risk can create sharp downside if a core driver underperforms.",
            "risk_reduction",
            "high",
        )

    # Reuse first actionable insights as fallback when explicit signal wins are sparse.
    for i in insights:
        title = str(i.get("title") or "").strip()
        action = str(i.get("action") or "").strip()
        priority = str(i.get("priority") or "medium").strip().lower()
        if not title or not action:
            continue
        add(
            title=title,
            rationale=action,
            impact_type="revenue_opportunity",
            priority=priority if priority in {"high", "medium", "low"} else "medium",
        )
        if len(out) >= 6:
            break

    priority_weight = {"high": 3, "medium": 2, "low": 1}
    out.sort(key=lambda x: (-priority_weight.get(str(x.get("priority")), 1), str(x.get("title", ""))))
    return out[:6]
