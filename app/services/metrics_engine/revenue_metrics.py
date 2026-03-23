"""Revenue-oriented aggregates (extend with time windows, cohorts, etc.)."""

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
    net_total = sum((o.net_revenue or Decimal("0")) for o in orders)
    gross_total = sum((o.total_price or Decimal("0")) for o in orders)
    discount_total = sum((o.discount_amount or Decimal("0")) for o in orders)
    refund_total = sum((o.refunded_amount or Decimal("0")) for o in orders)
    shipping_total = sum((o.shipping_amount or Decimal("0")) for o in orders)
    tax_total = sum((o.tax_amount or Decimal("0")) for o in orders)

    discount_to_gross = (
        (discount_total / gross_total) if gross_total and gross_total > 0 else Decimal("0")
    )

    return [
        build_snapshot(upload_id, "net_revenue_total", net_total),
        build_snapshot(upload_id, "gross_revenue_total", gross_total),
        build_snapshot(upload_id, "discount_total", discount_total),
        build_snapshot(upload_id, "refund_total", refund_total),
        build_snapshot(upload_id, "shipping_total", shipping_total),
        build_snapshot(upload_id, "tax_total", tax_total),
        build_snapshot(upload_id, "order_count", len(orders)),
        build_snapshot(upload_id, "discount_to_gross_ratio", discount_to_gross),
    ]
