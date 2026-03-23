"""Order-process metrics (AOV, status mix — extend over time)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.metric_snapshot import MetricSnapshot
from app.repositories.order_repository import OrderRepository

from app.services.metrics_engine.snapshots import build_snapshot


def collect(session: Session, upload_id: int) -> Sequence[MetricSnapshot]:
    repo = OrderRepository(session)
    orders = repo.list_orders_for_upload(upload_id)
    n = len(orders)
    net_total = sum((o.net_revenue or Decimal("0")) for o in orders)
    aov = (net_total / Decimal(n)) if n else Decimal("0")

    return [build_snapshot(upload_id, "average_order_value_net", aov)]
