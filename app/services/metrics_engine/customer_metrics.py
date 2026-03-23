"""Customer repeat / concentration placeholders (extend with identity graph)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.metric_snapshot import MetricSnapshot
from app.repositories.order_repository import OrderRepository

from app.services.metrics_engine.snapshots import build_snapshot


def collect(session: Session, upload_id: int) -> Sequence[MetricSnapshot]:
    repo = OrderRepository(session)
    orders = repo.list_orders_for_upload(upload_id)
    by_email: dict[str, int] = defaultdict(int)
    for o in orders:
        if o.customer and o.customer.email:
            by_email[o.customer.email] += 1
    repeat_customers = sum(1 for _, c in by_email.items() if c > 1)
    unique = len(by_email) or 1
    repeat_ratio = Decimal(repeat_customers) / Decimal(unique)

    return [build_snapshot(upload_id, "repeat_customer_ratio", repeat_ratio)]
