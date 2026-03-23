"""Advanced analytics metrics (pure functions, Decimal-safe).

These metrics extend the base revenue/orders/products/customers domains with:
- month-level trends
- SKU / source distributions
- pairing / bundling signals
- pricing + discount diagnostics
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from itertools import combinations
from typing import Any


@dataclass(frozen=True)
class AdvancedMetricConfig:
    free_shipping_threshold: Decimal = Decimal("60")
    free_shipping_near_window_ratio: Decimal = Decimal("0.10")  # 10% below threshold


def _to_decimal(v: Any) -> Decimal:
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def _to_decimal_if_present(v: Any) -> Decimal | None:
    if v is None:
        return None
    return _to_decimal(v)


def _to_int(v: Any) -> int:
    if v is None:
        return 0
    try:
        return int(v)
    except Exception:
        try:
            return int(float(str(v)))
        except Exception:
            return 0


def _month_key(order_date: Any) -> str | None:
    if not order_date:
        return None

    if isinstance(order_date, datetime):
        return order_date.strftime("%Y-%m")

    if isinstance(order_date, str):
        s = order_date.strip()
        if not s:
            return None
        # Shopify exports are usually parseable by fromisoformat; fall back gently.
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m")
        except Exception:
            pass
    return None


def _order_value(o: dict[str, Any]) -> Decimal:
    # Prefer net_revenue (already refund-adjusted), but fall back safely.
    net = o.get("net_revenue")
    if net is not None:
        return _to_decimal(net)
    total = o.get("total_price")
    return _to_decimal(total)


def compute_monthly_metrics(
    orders: list[dict[str, Any]],
) -> tuple[dict[str, Decimal], dict[str, int], dict[str, Decimal]]:
    monthly_rev: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    monthly_orders: dict[str, int] = defaultdict(int)

    for o in orders:
        mk = _month_key(o.get("order_date"))
        if not mk:
            continue
        monthly_rev[mk] += _order_value(o)
        monthly_orders[mk] += 1

    monthly_aov: dict[str, Decimal] = {}
    for mk in sorted(monthly_orders.keys()):
        count = monthly_orders.get(mk, 0)
        monthly_aov[mk] = monthly_rev.get(mk, Decimal("0")) / Decimal(count) if count > 0 else Decimal("0")

    months_sorted = sorted(monthly_orders.keys())
    monthly_rev_out = {mk: monthly_rev.get(mk, Decimal("0")) for mk in months_sorted}
    monthly_orders_out = {mk: monthly_orders.get(mk, 0) for mk in months_sorted}
    return monthly_rev_out, monthly_orders_out, monthly_aov


def compute_sku_metrics(order_items: list[dict[str, Any]]) -> dict[str, Any]:
    revenue_by_sku: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    blank_sku_revenue = Decimal("0")

    for it in order_items:
        sku_raw = it.get("sku")
        sku = str(sku_raw).strip() if sku_raw is not None else ""

        line_rev = it.get("net_line_revenue")
        if line_rev is None:
            line_rev = it.get("line_total")
        rev = _to_decimal(line_rev)

        revenue_by_sku[sku] += rev
        if not sku:
            blank_sku_revenue += rev

    total_revenue = sum(revenue_by_sku.values(), start=Decimal("0"))
    # For "top SKU" ignore blanks so the metric stays actionable.
    top_non_blank_revenue = max(
        (v for k, v in revenue_by_sku.items() if k),
        default=Decimal("0"),
    )
    top_sku_revenue_share = top_non_blank_revenue / total_revenue if total_revenue > 0 else Decimal("0")

    return {
        "top_sku_revenue_share": top_sku_revenue_share,
        "sku_revenue_distribution": dict(revenue_by_sku),
        "blank_sku_revenue": blank_sku_revenue,
    }


def compute_order_value_distribution(
    orders: list[dict[str, Any]],
) -> tuple[dict[str, int], Decimal]:
    buckets = {
        "<25": 0,
        "25-50": 0,
        "50-100": 0,
        "100-200": 0,
        ">200": 0,
    }

    total_orders = len(orders)
    low_value_count = 0
    for o in orders:
        v = _order_value(o)
        if v < Decimal("25"):
            buckets["<25"] += 1
        elif v < Decimal("50"):
            buckets["25-50"] += 1
        elif v < Decimal("100"):
            buckets["50-100"] += 1
        elif v < Decimal("200"):
            buckets["100-200"] += 1
        else:
            buckets[">200"] += 1

        if v < Decimal("50"):
            low_value_count += 1

    low_value_order_ratio = (
        (Decimal(low_value_count) / Decimal(total_orders)) if total_orders > 0 else Decimal("0")
    )
    return buckets, low_value_order_ratio


def compute_free_shipping_threshold_ratio(
    orders: list[dict[str, Any]],
    *,
    threshold: Decimal,
    window_ratio: Decimal,
) -> Decimal:
    # "Within 10% below threshold" => [threshold*(1-window), threshold)
    total_orders = len(orders)
    if total_orders == 0:
        return Decimal("0")

    lower_bound = threshold * (Decimal("1") - window_ratio)
    count = 0
    for o in orders:
        v = _order_value(o)
        if lower_bound <= v < threshold:
            count += 1

    return Decimal(count) / Decimal(total_orders)


def compute_discount_metrics(orders: list[dict[str, Any]], order_items: list[dict[str, Any]]) -> dict[str, Any]:
    discount_amount_total = sum((_to_decimal(o.get("discount_amount")) for o in orders), start=Decimal("0"))
    gross_revenue = sum((_to_decimal(o.get("total_price")) for o in orders), start=Decimal("0"))
    discount_rate = discount_amount_total / gross_revenue if gross_revenue > 0 else Decimal("0")

    # Sum(compare_at_price - price) across units (qty-weighted when available).
    compare_at_discount_total = Decimal("0")
    for it in order_items:
        compare_at_raw = it.get("compare_at_price")
        price_raw = it.get("unit_price")
        if compare_at_raw is None or price_raw is None:
            continue
        compare_at = _to_decimal(compare_at_raw)
        price = _to_decimal(price_raw)
        qty = _to_int(it.get("quantity"))
        compare_at_discount_total += (compare_at - price) * Decimal(max(qty, 0))

    return {
        "discount_amount_total": discount_amount_total,
        "discount_rate": discount_rate,
        "compare_at_discount_total": compare_at_discount_total,
    }


def compute_bundle_pairs(order_items: list[dict[str, Any]]) -> list[tuple[str, str, int]]:
    # "Bought together" => two distinct SKUs appearing in the same order.
    skus_by_order: dict[str, set[str]] = defaultdict(set)
    for it in order_items:
        order_name = it.get("order_name")
        if not order_name:
            continue
        sku_raw = it.get("sku")
        sku = str(sku_raw).strip() if sku_raw is not None else ""
        if not sku:
            continue
        skus_by_order[str(order_name)].add(sku)

    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for skus in skus_by_order.values():
        if len(skus) < 2:
            continue
        for a, b in combinations(sorted(skus), 2):
            pair_counts[(a, b)] += 1

    top_pairs = sorted(pair_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    return [(sku1, sku2, cnt) for (sku1, sku2), cnt in top_pairs]


def compute_source_metrics(orders: list[dict[str, Any]]) -> dict[str, Any]:
    revenue_by_source: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for o in orders:
        src_raw = o.get("source_name")
        src = str(src_raw).strip() if src_raw is not None else ""
        src_key = src if src else "UNKNOWN"
        revenue_by_source[src_key] += _order_value(o)

    total_revenue = sum(revenue_by_source.values(), start=Decimal("0"))
    top_source_revenue = max(revenue_by_source.values(), default=Decimal("0"))
    top_source_share = top_source_revenue / total_revenue if total_revenue > 0 else Decimal("0")
    return {
        "source_revenue_distribution": dict(revenue_by_source),
        "top_source_share": top_source_share,
    }


def compute_growth_metrics(orders: list[dict[str, Any]]) -> dict[str, Any]:
    monthly_rev, monthly_orders, monthly_aov = compute_monthly_metrics(orders)
    months = sorted(monthly_rev.keys())
    if len(months) < 2:
        return {
            "revenue_growth": Decimal("0"),
            "aov_growth": Decimal("0"),
        }

    last_month = months[-1]
    prev_month = months[-2]

    rev_prev = monthly_rev.get(prev_month, Decimal("0"))
    rev_last = monthly_rev.get(last_month, Decimal("0"))
    revenue_growth = (rev_last - rev_prev) / rev_prev if rev_prev > 0 else Decimal("0")

    aov_prev = monthly_aov.get(prev_month, Decimal("0"))
    aov_last = monthly_aov.get(last_month, Decimal("0"))
    aov_growth = (aov_last - aov_prev) / aov_prev if aov_prev > 0 else Decimal("0")

    return {
        "revenue_growth": revenue_growth,
        "aov_growth": aov_growth,
    }


def compute_advanced_metrics(
    orders: list[dict[str, Any]],
    order_items: list[dict[str, Any]],
    config: AdvancedMetricConfig | None = None,
) -> dict[str, Any]:
    cfg = config or AdvancedMetricConfig()

    monthly_rev, monthly_orders, monthly_aov = compute_monthly_metrics(orders)
    sku_metrics = compute_sku_metrics(order_items)
    value_buckets, low_value_order_ratio = compute_order_value_distribution(orders)
    discount_metrics = compute_discount_metrics(orders, order_items)
    bundle_pairs = compute_bundle_pairs(order_items)
    source_metrics = compute_source_metrics(orders)
    near_free_shipping = compute_free_shipping_threshold_ratio(
        orders,
        threshold=cfg.free_shipping_threshold,
        window_ratio=cfg.free_shipping_near_window_ratio,
    )
    growth_metrics = compute_growth_metrics(orders)

    return {
        "monthly_revenue": monthly_rev,
        "monthly_orders": monthly_orders,
        "monthly_aov": monthly_aov,
        "top_sku_revenue_share": sku_metrics["top_sku_revenue_share"],
        "sku_revenue_distribution": sku_metrics["sku_revenue_distribution"],
        "order_value_distribution": value_buckets,
        "low_value_order_ratio": low_value_order_ratio,
        **discount_metrics,
        "bundle_pairs": bundle_pairs,
        **source_metrics,
        "blank_sku_revenue": sku_metrics["blank_sku_revenue"],
        "orders_near_free_shipping_threshold": near_free_shipping,
        **growth_metrics,
    }

