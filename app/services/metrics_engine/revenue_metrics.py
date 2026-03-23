"""Revenue-oriented aggregates (extend with time windows, cohorts, etc.)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models.metric_snapshot import MetricSnapshot
from app.repositories.order_repository import OrderRepository


def collect(session: Session, upload_id: int) -> Sequence[MetricSnapshot]:
    """Example metric group: totals and discount pressure."""
    repo = OrderRepository(session)
    orders = repo.list_orders_for_upload(upload_id)
    net_total = sum((o.net_revenue or 0) for o in orders)
    gross_total = sum((o.total_amount or 0) for o in orders)
    discount_total = sum((o.discount_amount or 0) for o in orders)
    refund_total = sum((o.refund_amount or 0) for o in orders)
    shipping_total = sum((o.shipping_amount or 0) for o in orders)
    tax_total = sum((o.tax_amount or 0) for o in orders)

    discount_to_gross = (discount_total / gross_total) if gross_total else 0.0

    def snap(key: str, val: float) -> MetricSnapshot:
        return MetricSnapshot(
            upload_id=upload_id,
            metric_key=key,
            dimension_key=None,
            value_numeric=val,
            value_json=None,
        )

    return [
        snap("net_revenue_total", float(net_total)),
        snap("gross_revenue_total", float(gross_total)),
        snap("discount_total", float(discount_total)),
        snap("refund_total", float(refund_total)),
        snap("shipping_total", float(shipping_total)),
        snap("tax_total", float(tax_total)),
        snap("order_count", float(len(orders))),
        snap("discount_to_gross_ratio", float(discount_to_gross)),
    ]
