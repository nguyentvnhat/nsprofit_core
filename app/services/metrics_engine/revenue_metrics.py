"""Revenue domain metrics (pure functions, Decimal-safe)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def _to_decimal(v: Any) -> Decimal:
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def _median(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    vs = sorted(values)
    n = len(vs)
    mid = n // 2
    if n % 2 == 1:
        return vs[mid]
    return (vs[mid - 1] + vs[mid]) / Decimal("2")


def compute_revenue_metrics(orders: list[dict[str, Any]]) -> dict[str, Any]:
    total_orders = len(orders)
    gross_values = [_to_decimal(o.get("total_price")) for o in orders]
    net_values = [_to_decimal(o.get("net_revenue")) for o in orders]
    gross_revenue = sum(gross_values, start=Decimal("0"))
    net_revenue = sum(net_values, start=Decimal("0"))
    total_discounts = sum((_to_decimal(o.get("discount_amount")) for o in orders), start=Decimal("0"))
    total_refunds = sum((_to_decimal(o.get("refunded_amount")) for o in orders), start=Decimal("0"))
    total_shipping = sum((_to_decimal(o.get("shipping_amount")) for o in orders), start=Decimal("0"))
    total_tax = sum((_to_decimal(o.get("tax_amount")) for o in orders), start=Decimal("0"))
    discount_to_gross_ratio = (
        total_discounts / gross_revenue if gross_revenue > 0 else Decimal("0")
    )
    aov = net_revenue / Decimal(total_orders) if total_orders > 0 else Decimal("0")
    median_order_value = _median(net_values)

    return {
        "total_orders": total_orders,
        "gross_revenue": gross_revenue,
        "net_revenue": net_revenue,
        "total_discounts": total_discounts,
        "total_refunds": total_refunds,
        "total_shipping": total_shipping,
        "total_tax": total_tax,
        "discount_to_gross_ratio": discount_to_gross_ratio,
        "aov": aov,
        "median_order_value": median_order_value,
    }
