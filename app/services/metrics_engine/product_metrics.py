"""Product metrics (pure functions, SKU-level breakdowns)."""

from __future__ import annotations

from collections import defaultdict
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


def compute_product_metrics(
    orders: list[dict[str, Any]],
    order_items: list[dict[str, Any]],
) -> dict[str, Any]:
    _ = orders  # reserved for future order-level product joins
    revenue_by_sku: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    units_by_sku: dict[str, int] = defaultdict(int)
    discount_by_sku: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    refund_by_sku: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for it in order_items:
        sku = str(it.get("sku") or "UNKNOWN")
        units_raw = it.get("quantity")
        try:
            units = int(units_raw) if units_raw is not None else 0
        except Exception:
            units = 0
        line_total = _to_decimal(it.get("line_total"))
        net_line = _to_decimal(it.get("net_line_revenue"))
        line_discount = _to_decimal(it.get("line_discount_amount"))
        line_refund = line_total - net_line if line_total > net_line else Decimal("0")

        revenue_by_sku[sku] += net_line
        units_by_sku[sku] += max(units, 0)
        discount_by_sku[sku] += line_discount
        refund_by_sku[sku] += line_refund

    total_product_revenue = sum(revenue_by_sku.values(), start=Decimal("0"))
    top3_revenue = sum(sorted(revenue_by_sku.values(), reverse=True)[:3], start=Decimal("0"))
    top_3_sku_share = (
        top3_revenue / total_product_revenue if total_product_revenue > 0 else Decimal("0")
    )

    total_discounts = sum(discount_by_sku.values(), start=Decimal("0"))
    gross_proxy = total_product_revenue + total_discounts
    product_discount_rate = total_discounts / gross_proxy if gross_proxy > 0 else Decimal("0")

    total_refunds = sum(refund_by_sku.values(), start=Decimal("0"))
    product_refund_rate = total_refunds / gross_proxy if gross_proxy > 0 else Decimal("0")

    return {
        "product_revenue": dict(revenue_by_sku),
        "product_units": dict(units_by_sku),
        "top_3_sku_share": top_3_sku_share,
        "product_discount_rate": product_discount_rate,
        "product_refund_rate": product_refund_rate,
    }
