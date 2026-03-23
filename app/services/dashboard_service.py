"""Read-model helpers for Streamlit (no business rules here — query + shape only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.upload import Upload
from app.repositories import InsightRepository, OrderRepository, UploadRepository
from app.repositories.metric_repository import MetricRepository
from app.repositories.signal_repository import SignalRepository


@dataclass
class OverviewDTO:
    upload_id: int
    file_name: str
    status: str
    kpis: dict[str, float]
    orders_sample: pd.DataFrame
    insights: list[dict[str, Any]]
    signals: list[dict[str, Any]]


def _latest_upload_id(session: Session) -> int | None:
    uid = session.scalars(select(Upload.id).order_by(Upload.id.desc()).limit(1)).first()
    return int(uid) if uid is not None else None


def get_overview(session: Session, upload_id: int | None = None) -> OverviewDTO | None:
    uid = upload_id or _latest_upload_id(session)
    if uid is None:
        return None
    up_repo = UploadRepository(session)
    upload = up_repo.get(uid)
    if upload is None:
        return None

    m_repo = MetricRepository(session)
    snapshots: dict[str, float] = {}
    for s in m_repo.list_for_upload(uid):
        if (
            s.metric_scope == "overall"
            and s.period_type == "all_time"
            and s.dimension_1 is None
            and s.dimension_2 is None
        ):
            snapshots[s.metric_code] = float(s.metric_value)

    o_repo = OrderRepository(session)
    orders = o_repo.list_orders_for_upload(uid)
    rows = []
    for o in orders[:500]:
        rows.append(
            {
                "order": o.order_name,
                "net_revenue": float(o.net_revenue or 0),
                "total": float(o.total_price or 0),
                "discount": float(o.discount_amount or 0),
                "qty": int(o.total_quantity or 0),
                "customer": o.customer.email if o.customer else None,
                "order_date": o.order_date,
            }
        )
    orders_df = pd.DataFrame(rows)

    i_repo = InsightRepository(session)
    insights = [
        {
            "insight_code": i.insight_code,
            "category": i.category,
            "priority": i.priority,
            "title": i.title,
            "summary": i.summary,
            "implication_text": i.implication_text,
            "recommended_action": i.recommended_action,
        }
        for i in i_repo.list_for_upload(uid)
    ]

    s_repo = SignalRepository(session)
    signals = [
        {
            "entity_type": s.entity_type,
            "signal_code": s.signal_code,
            "severity": s.severity,
            "context": s.signal_context_json or {},
        }
        for s in s_repo.list_for_upload(uid)
    ]

    return OverviewDTO(
        upload_id=uid,
        file_name=upload.file_name,
        status=upload.status,
        kpis=snapshots,
        orders_sample=orders_df,
        insights=insights,
        signals=signals,
    )


def get_product_breakdown(session: Session, upload_id: int) -> pd.DataFrame:
    o_repo = OrderRepository(session)
    orders = o_repo.list_orders_for_upload(upload_id)
    rows: list[dict[str, Any]] = []
    for o in orders:
        for li in o.items:
            rows.append(
                {
                    "sku": li.sku,
                    "product_name": li.product_name,
                    "quantity": li.quantity,
                    "line_total": float(li.line_total or 0),
                    "order": o.order_name,
                }
            )
    return pd.DataFrame(rows)


def get_customer_breakdown(session: Session, upload_id: int) -> pd.DataFrame:
    o_repo = OrderRepository(session)
    orders = o_repo.list_orders_for_upload(upload_id)
    agg: dict[str, dict[str, Any]] = {}
    for o in orders:
        key = o.customer.email if o.customer and o.customer.email else f"guest:{o.id}"
        bucket = agg.setdefault(
            key,
            {"email": o.customer.email if o.customer else None, "orders": 0, "net": 0.0},
        )
        bucket["orders"] += 1
        bucket["net"] += float(o.net_revenue or 0)
    return pd.DataFrame(list(agg.values()))


def list_uploads(session: Session, limit: int = 50) -> list[dict[str, Any]]:
    stmt = select(Upload).order_by(Upload.id.desc()).limit(limit)
    ups = session.scalars(stmt).all()
    return [
        {"id": u.id, "file_name": u.file_name, "status": u.status, "row_count": u.row_count}
        for u in ups
    ]
