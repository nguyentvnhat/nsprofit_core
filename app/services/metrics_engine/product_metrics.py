"""Product / SKU concentration metrics."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models.metric_snapshot import MetricSnapshot
from app.repositories.order_repository import OrderRepository


def collect(session: Session, upload_id: int) -> Sequence[MetricSnapshot]:
    repo = OrderRepository(session)
    orders = repo.list_orders_for_upload(upload_id)
    qty_by_sku: dict[str, float] = defaultdict(float)
    revenue_by_sku: dict[str, float] = defaultdict(float)
    for o in orders:
        for li in o.items:
            key = li.sku or li.title or "UNKNOWN"
            qty_by_sku[key] += float(li.quantity or 0)
            revenue_by_sku[key] += float(li.line_total or 0)

    total_qty = sum(qty_by_sku.values()) or 1.0
    top_share = max(qty_by_sku.values(), default=0) / total_qty

    return [
        MetricSnapshot(
            upload_id=upload_id,
            metric_key="top_sku_quantity_share",
            dimension_key=None,
            value_numeric=float(top_share),
            value_json={"qty_by_sku": dict(qty_by_sku), "revenue_by_sku": dict(revenue_by_sku)},
        )
    ]
