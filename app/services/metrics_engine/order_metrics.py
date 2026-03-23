"""Order-quality metrics (pure functions, configurable thresholds)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class OrderMetricConfig:
    low_value_threshold: Decimal = Decimal("20")
    high_value_threshold: Decimal = Decimal("200")


def _to_decimal(v: Any) -> Decimal:
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def compute_order_metrics(
    orders: list[dict[str, Any]],
    *,
    config: OrderMetricConfig | None = None,
) -> dict[str, Any]:
    cfg = config or OrderMetricConfig()
    total_orders = len(orders)

    total_units = 0
    discounted = 0
    refunded = 0
    free_shipping = 0
    low_value = 0
    high_value = 0

    for o in orders:
        qty = o.get("total_quantity")
        try:
            total_units += int(qty) if qty is not None else 0
        except Exception:
            pass

        discount = _to_decimal(o.get("discount_amount"))
        refund = _to_decimal(o.get("refunded_amount"))
        shipping = _to_decimal(o.get("shipping_amount"))
        order_value = _to_decimal(o.get("net_revenue"))
        if order_value == 0:
            order_value = _to_decimal(o.get("total_price"))

        if discount > 0:
            discounted += 1
        if refund > 0:
            refunded += 1
        if shipping == 0:
            free_shipping += 1
        if order_value < cfg.low_value_threshold:
            low_value += 1
        if order_value > cfg.high_value_threshold:
            high_value += 1

    denom = Decimal(total_orders) if total_orders > 0 else Decimal("1")
    avg_units = Decimal(total_units) / denom if total_orders > 0 else Decimal("0")

    return {
        "total_units_sold": total_units,
        "average_units_per_order": avg_units,
        "discounted_order_rate": Decimal(discounted) / denom if total_orders > 0 else Decimal("0"),
        "refunded_order_rate": Decimal(refunded) / denom if total_orders > 0 else Decimal("0"),
        "free_shipping_rate": Decimal(free_shipping) / denom if total_orders > 0 else Decimal("0"),
        "low_value_order_rate": Decimal(low_value) / denom if total_orders > 0 else Decimal("0"),
        "high_value_order_rate": Decimal(high_value) / denom if total_orders > 0 else Decimal("0"),
        "thresholds": {
            "low_value_threshold": cfg.low_value_threshold,
            "high_value_threshold": cfg.high_value_threshold,
        },
    }
