"""Discount/promotion-oriented metrics (store-level scalars).

These metrics are designed to support rules/signals for discount recommendation
without requiring inventory or on-site conversion events.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any


def _to_date(value: object | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def compute_discount_metrics(orders: list[dict[str, Any]], order_items: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Return store-level scalar metrics used by rules/signals.

    Requires only order dates + SKU quantities from the normalized dataset.
    """
    order_day: dict[str, date] = {}
    max_day: date | None = None
    for o in orders:
        name = str(o.get("order_name") or "")
        d = _to_date(o.get("order_date"))
        if not name or d is None:
            continue
        order_day[name] = d
        if max_day is None or d > max_day:
            max_day = d
    if max_day is None:
        max_day = date.today()

    w7 = max_day - timedelta(days=7)
    w30 = max_day - timedelta(days=30)

    sku_units_7d: dict[str, int] = defaultdict(int)
    sku_units_30d: dict[str, int] = defaultdict(int)
    sku_last_day_ord: dict[str, int] = defaultdict(lambda: -1)
    active_30d_skus: set[str] = set()

    for it in order_items:
        sku = str(it.get("sku") or "UNKNOWN").strip() or "UNKNOWN"
        qty = int(it.get("quantity") or 0)
        if qty <= 0:
            continue
        on = str(it.get("order_name") or "")
        d = order_day.get(on)
        if d is None:
            continue
        if d >= w30:
            sku_units_30d[sku] += qty
            active_30d_skus.add(sku)
        if d >= w7:
            sku_units_7d[sku] += qty
        sku_last_day_ord[sku] = max(sku_last_day_ord[sku], d.toordinal())

    active_count = len(active_30d_skus)
    if active_count <= 0:
        return {
            "active_sku_count_30d": 0,
            "slow_mover_sku_share": 0.0,
            "fast_mover_sku_share": 0.0,
            "avg_days_since_last_sale_active_30d": 0.0,
        }

    slow = 0
    fast = 0
    days_sum = 0
    days_n = 0
    for sku in active_30d_skus:
        u7 = int(sku_units_7d.get(sku, 0))
        u30 = int(sku_units_30d.get(sku, 0))
        if u30 > 0 and u7 <= 0:
            slow += 1
        if u7 >= 5:
            fast += 1
        last_ord = int(sku_last_day_ord.get(sku, -1))
        if last_ord >= 0:
            days_sum += int((max_day - date.fromordinal(last_ord)).days)
            days_n += 1

    return {
        "active_sku_count_30d": float(active_count),
        "slow_mover_sku_share": float(slow) / float(active_count),
        "fast_mover_sku_share": float(fast) / float(active_count),
        "avg_days_since_last_sale_active_30d": (float(days_sum) / float(days_n)) if days_n else 0.0,
    }

