"""Customer metrics (pure functions)."""

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


def compute_customer_metrics(
    orders: list[dict[str, Any]],
    customers: list[dict[str, Any]],
) -> dict[str, Any]:
    # Canonical identity key prefers email, then explicit customer id.
    def customer_key(o: dict[str, Any]) -> str | None:
        email = o.get("customer_email")
        if email:
            return str(email)
        cid = o.get("customer_id")
        return str(cid) if cid is not None else None

    order_counts: dict[str, int] = defaultdict(int)
    revenue_by_customer: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for o in orders:
        key = customer_key(o)
        if not key:
            continue
        order_counts[key] += 1
        revenue_by_customer[key] += _to_decimal(o.get("net_revenue"))

    total_customers = len(customers) if customers else len(order_counts)
    if total_customers == 0:
        total_customers = len(order_counts)

    new_customer_count = 0
    repeat_customer_count = 0
    if customers:
        for c in customers:
            ocount = c.get("total_orders")
            try:
                n = int(ocount) if ocount is not None else order_counts.get(str(c.get("email")), 1)
            except Exception:
                n = 1
            if n > 1:
                repeat_customer_count += 1
            else:
                new_customer_count += 1
    else:
        for n in order_counts.values():
            if n > 1:
                repeat_customer_count += 1
            else:
                new_customer_count += 1

    # Segment AOV by order flag if present; fallback to customer repeat inferred from counts.
    new_net = Decimal("0")
    new_orders = 0
    repeat_net = Decimal("0")
    repeat_orders = 0
    for o in orders:
        key = customer_key(o)
        net = _to_decimal(o.get("net_revenue"))
        is_repeat = bool(o.get("is_repeat_customer"))
        if not o.get("is_repeat_customer") and key:
            is_repeat = order_counts.get(key, 0) > 1
        if is_repeat:
            repeat_net += net
            repeat_orders += 1
        else:
            new_net += net
            new_orders += 1

    repeat_customer_rate = (
        Decimal(repeat_customer_count) / Decimal(total_customers)
        if total_customers > 0
        else Decimal("0")
    )
    new_customer_aov = new_net / Decimal(new_orders) if new_orders > 0 else Decimal("0")
    repeat_customer_aov = repeat_net / Decimal(repeat_orders) if repeat_orders > 0 else Decimal("0")

    total_customer_revenue = sum(revenue_by_customer.values(), start=Decimal("0"))
    top_customer_revenue = max(revenue_by_customer.values(), default=Decimal("0"))
    top_customer_revenue_share = (
        top_customer_revenue / total_customer_revenue if total_customer_revenue > 0 else Decimal("0")
    )

    return {
        "total_customers": total_customers,
        "new_customer_count": new_customer_count,
        "repeat_customer_count": repeat_customer_count,
        "repeat_customer_rate": repeat_customer_rate,
        "new_customer_AOV": new_customer_aov,
        "repeat_customer_AOV": repeat_customer_aov,
        "top_customer_revenue_share": top_customer_revenue_share,
    }
