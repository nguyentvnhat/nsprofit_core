"""Shared dashboard service for Streamlit pages."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.upload import Upload
from app.repositories import InsightRepository, OrderRepository, UploadRepository
from app.repositories.metric_repository import MetricRepository
from app.repositories.signal_repository import SignalRepository
from app.services.pipeline import process_shopify_csv


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
    customer_summary: dict[str, float]
    top_customers: pd.DataFrame
    signals_by_severity: dict[str, list[dict[str, Any]]]
    insights: list[dict[str, Any]]


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
    products_table, revenue_by_sku, top_3_sku_share = _build_products(session, uid)
    customer_summary, top_customers = _build_customers(orders_df)
    signals_by_severity = _build_signals(session, uid)
    insights = _build_insights(session, uid)

    kpis = {
        "total_revenue": metrics_map.get("gross_revenue", 0.0),
        "net_revenue": metrics_map.get("net_revenue", 0.0),
        "aov": metrics_map.get("aov", 0.0),
        "total_orders": metrics_map.get("total_orders", 0.0),
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
        customer_summary=customer_summary,
        top_customers=top_customers,
        signals_by_severity=signals_by_severity,
        insights=insights,
    )


def _load_metric_snapshots(session: Session, upload_id: int) -> dict[str, float]:
    rows = MetricRepository(session).list_for_upload(upload_id)
    out: dict[str, float] = {}
    for s in rows:
        if (
            s.metric_scope == "overall"
            and s.period_type == "all_time"
            and s.dimension_1 is None
            and s.dimension_2 is None
        ):
            out[s.metric_code] = float(s.metric_value)
    return out


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
) -> tuple[pd.DataFrame, pd.DataFrame, float]:
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
        return empty, pd.DataFrame(columns=["revenue"]), 0.0

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
    return grouped, revenue_by_sku, top3_share


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


def _build_insights(session: Session, upload_id: int) -> list[dict[str, Any]]:
    rows = InsightRepository(session).list_for_upload(upload_id)
    return [
        {
            "insight_code": i.insight_code,
            "category": i.category,
            "priority": i.priority,
            "title": i.title,
            "summary": i.summary,
            "implication": i.implication_text,
            "action": i.recommended_action,
        }
        for i in rows
    ]
