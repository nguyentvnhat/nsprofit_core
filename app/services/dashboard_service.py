"""Read-model helpers for Streamlit (no business rules here — query + shape only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.repositories import InsightRepository, OrderRepository, UploadRepository
from app.repositories.metric_repository import MetricRepository
from app.repositories.signal_repository import SignalRepository


@dataclass
class OverviewDTO:
    upload_id: int
    filename: str
    status: str
    kpis: dict[str, float]
    orders_sample: pd.DataFrame
    insights: list[dict[str, Any]]
    signals: list[dict[str, Any]]


def _latest_upload_id(session: Session) -> int | None:
    # Simple MVP: highest id wins; replace with tenant + created_at filter later.
    repo = UploadRepository(session)
    from sqlalchemy import select

    from app.models.upload import Upload

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
        if s.dimension_key is None and s.value_numeric is not None:
            snapshots[s.metric_key] = float(s.value_numeric)

    o_repo = OrderRepository(session)
    orders = o_repo.list_orders_for_upload(uid)
    rows = []
    for o in orders[:500]:
        rows.append(
            {
                "order": o.external_name,
                "net_revenue": float(o.net_revenue or 0),
                "total": float(o.total_amount or 0),
                "discount": float(o.discount_amount or 0),
                "qty": int(o.total_quantity or 0),
                "customer": o.customer.email if o.customer else None,
                "processed_at": o.processed_at,
            }
        )
    orders_df = pd.DataFrame(rows)

    i_repo = InsightRepository(session)
    insights = [
        {
            "rule_id": i.rule_id,
            "title": i.title,
            "summary": i.summary,
            "implication": i.implication,
            "action": i.action,
            "severity": i.severity,
        }
        for i in i_repo.list_for_upload(uid)
    ]

    s_repo = SignalRepository(session)
    signals = [
        {"domain": s.domain, "code": s.code, "severity": s.severity, "payload": s.payload or {}}
        for s in s_repo.list_for_upload(uid)
    ]

    return OverviewDTO(
        upload_id=uid,
        filename=upload.filename,
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
                    "title": li.title,
                    "quantity": li.quantity,
                    "line_total": float(li.line_total or 0),
                    "order": o.external_name,
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
    from sqlalchemy import select

    from app.models.upload import Upload

    stmt = select(Upload).order_by(Upload.id.desc()).limit(limit)
    ups = session.scalars(stmt).all()
    return [
        {"id": u.id, "filename": u.filename, "status": u.status, "row_count": u.row_count}
        for u in ups
    ]
