"""Operational / financial risk signals (refunds, shipping)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.order_repository import OrderRepository

from app.services.signal_engine.types import SignalDraft

DEFAULT_REFUND_TO_GROSS_WARN = 0.12


def collect(
    session: Session,
    upload_id: int,
    metric_map: dict[str, float],
) -> Sequence[SignalDraft]:
    _ = metric_map
    out: list[SignalDraft] = []
    repo = OrderRepository(session)
    orders = repo.list_orders_for_upload(upload_id)
    gross = sum((o.total_price or Decimal("0")) for o in orders)
    refunds = sum((o.refunded_amount or Decimal("0")) for o in orders)
    ratio = float(refunds / gross) if gross and gross > 0 else 0.0
    if ratio >= DEFAULT_REFUND_TO_GROSS_WARN:
        out.append(
            SignalDraft(
                domain="risk",
                code="ELEVATED_REFUND_RATE",
                severity="warning",
                payload={"refund_to_gross_ratio": ratio, "threshold": DEFAULT_REFUND_TO_GROSS_WARN},
            )
        )

    free_ship_flags = 0
    for o in orders:
        ship = o.shipping_amount or Decimal("0")
        if ship == 0 and (o.total_quantity or 0) > 0:
            free_ship_flags += 1
    if len(orders) >= 10 and free_ship_flags / len(orders) > 0.65:
        out.append(
            SignalDraft(
                domain="risk",
                code="FREE_SHIPPING_HEAVY",
                severity="info",
                payload={"zero_shipping_order_share": free_ship_flags / len(orders)},
            )
        )
    return out
