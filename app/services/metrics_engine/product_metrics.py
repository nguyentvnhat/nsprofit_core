"""Product / SKU concentration metrics."""

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
    qty_by_sku: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for o in orders:
        for li in o.items:
            key = li.sku or li.product_name or "UNKNOWN"
            qty_by_sku[key] += Decimal(li.quantity or 0)

    total_qty = sum(qty_by_sku.values(), start=Decimal("0")) or Decimal("1")
    top_share = max(qty_by_sku.values(), default=Decimal("0")) / total_qty

    return [build_snapshot(upload_id, "top_sku_quantity_share", top_share)]
