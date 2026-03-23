"""Order-process metrics (AOV, status mix — extend over time)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models.metric_snapshot import MetricSnapshot
from app.repositories.order_repository import OrderRepository


def collect(session: Session, upload_id: int) -> Sequence[MetricSnapshot]:
    repo = OrderRepository(session)
    orders = repo.list_orders_for_upload(upload_id)
    n = len(orders)
    net_total = sum((o.net_revenue or 0) for o in orders)
    aov = (net_total / n) if n else 0.0

    return [
        MetricSnapshot(
            upload_id=upload_id,
            metric_key="average_order_value_net",
            dimension_key=None,
            value_numeric=float(aov),
            value_json=None,
        )
    ]
