"""Advanced metrics signal rules (pure functions)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.services.signal_engine.types import Signal

DEFAULTS: dict[str, float] = {
    "high_discount_dependency_rate": 0.2,
    "hero_sku_concentration_rate": 0.4,
    "low_order_value_problem_rate": 0.5,
    "free_shipping_opportunity_rate": 0.3,
    "source_concentration_risk_rate": 0.7,
    "bundle_pair_count_threshold": 2.0,
    "unstable_growth_abs_threshold": 0.3,
}


def _to_float(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except Exception:
        return 0.0


def _bool_signal(
    *,
    signal_code: str,
    category: str,
    severity: str,
    active: bool,
    signal_value: float,
    threshold_value: float,
    context: dict[str, Any],
) -> Signal:
    return {
        "signal_code": signal_code,
        "category": category,
        "severity": severity,
        "entity_type": "overall",
        "entity_key": None,
        "signal_value": signal_value,
        "threshold_value": threshold_value,
        "context": {"active": active, **context},
    }


def _extract_pair_count(pair: Any) -> int:
    if not isinstance(pair, (list, tuple)) or len(pair) < 3:
        return 0
    try:
        return int(pair[2])
    except Exception:
        return 0


def _max_abs_mom_growth(monthly_revenue: dict[str, Any]) -> float:
    months = sorted(str(k) for k in monthly_revenue.keys())
    if len(months) < 3:
        return 0.0

    max_abs = 0.0
    prev = _to_float(monthly_revenue.get(months[0]))
    for m in months[1:]:
        curr = _to_float(monthly_revenue.get(m))
        if prev > 0:
            growth = (curr - prev) / prev
            max_abs = max(max_abs, abs(growth))
        prev = curr
    return max_abs


def collect(metrics: dict[str, dict[str, Any]], config: dict[str, float] | None = None) -> list[Signal]:
    cfg = {**DEFAULTS, **(config or {})}
    adv = metrics.get("advanced", {})
    out: list[Signal] = []

    discount_rate = _to_float(adv.get("discount_rate"))
    high_discount_dependency = discount_rate > cfg["high_discount_dependency_rate"]
    out.append(
        _bool_signal(
            signal_code="HIGH_DISCOUNT_DEPENDENCY_V2",
            category="pricing",
            severity="high" if high_discount_dependency else "low",
            active=high_discount_dependency,
            signal_value=discount_rate,
            threshold_value=cfg["high_discount_dependency_rate"],
            context={"discount_rate": discount_rate},
        )
    )

    compare_at_discount_total = _to_float(adv.get("compare_at_discount_total"))
    discount_amount_total = _to_float(adv.get("discount_amount_total"))
    stacked_discounting = compare_at_discount_total > 0 and discount_amount_total > 0
    out.append(
        _bool_signal(
            signal_code="STACKED_DISCOUNTING",
            category="pricing",
            severity="medium" if stacked_discounting else "low",
            active=stacked_discounting,
            signal_value=1.0 if stacked_discounting else 0.0,
            threshold_value=1.0,
            context={
                "compare_at_discount_total": compare_at_discount_total,
                "discount_amount_total": discount_amount_total,
            },
        )
    )

    revenue_growth = _to_float(adv.get("revenue_growth"))
    aov_growth = _to_float(adv.get("aov_growth"))
    volume_driven_growth = revenue_growth > 0 and aov_growth <= 0
    out.append(
        _bool_signal(
            signal_code="VOLUME_DRIVEN_GROWTH",
            category="growth_quality",
            severity="medium" if volume_driven_growth else "low",
            active=volume_driven_growth,
            signal_value=1.0 if volume_driven_growth else 0.0,
            threshold_value=1.0,
            context={"revenue_growth": revenue_growth, "aov_growth": aov_growth},
        )
    )

    top_sku_revenue_share = _to_float(adv.get("top_sku_revenue_share"))
    hero_sku_concentration = top_sku_revenue_share > cfg["hero_sku_concentration_rate"]
    out.append(
        _bool_signal(
            signal_code="HERO_SKU_CONCENTRATION",
            category="product_mix",
            severity="high" if hero_sku_concentration else "low",
            active=hero_sku_concentration,
            signal_value=top_sku_revenue_share,
            threshold_value=cfg["hero_sku_concentration_rate"],
            context={"top_sku_revenue_share": top_sku_revenue_share},
        )
    )

    low_value_order_ratio = _to_float(adv.get("low_value_order_ratio"))
    low_order_value_problem = low_value_order_ratio > cfg["low_order_value_problem_rate"]
    out.append(
        _bool_signal(
            signal_code="LOW_ORDER_VALUE_PROBLEM",
            category="basket",
            severity="high" if low_order_value_problem else "low",
            active=low_order_value_problem,
            signal_value=low_value_order_ratio,
            threshold_value=cfg["low_order_value_problem_rate"],
            context={"low_value_order_ratio": low_value_order_ratio},
        )
    )

    near_free_shipping = _to_float(adv.get("orders_near_free_shipping_threshold"))
    free_shipping_opportunity = near_free_shipping > cfg["free_shipping_opportunity_rate"]
    out.append(
        _bool_signal(
            signal_code="FREE_SHIPPING_OPPORTUNITY",
            category="pricing_lever",
            severity="medium" if free_shipping_opportunity else "low",
            active=free_shipping_opportunity,
            signal_value=near_free_shipping,
            threshold_value=cfg["free_shipping_opportunity_rate"],
            context={"orders_near_free_shipping_threshold": near_free_shipping},
        )
    )

    top_source_share = _to_float(adv.get("top_source_share"))
    source_concentration_risk = top_source_share > cfg["source_concentration_risk_rate"]
    out.append(
        _bool_signal(
            signal_code="SOURCE_CONCENTRATION_RISK",
            category="channel_risk",
            severity="high" if source_concentration_risk else "low",
            active=source_concentration_risk,
            signal_value=top_source_share,
            threshold_value=cfg["source_concentration_risk_rate"],
            context={"top_source_share": top_source_share},
        )
    )

    bundle_pairs = adv.get("bundle_pairs", [])
    max_pair_count = max((_extract_pair_count(p) for p in bundle_pairs), default=0)
    threshold = int(cfg["bundle_pair_count_threshold"])
    bundle_opportunity = max_pair_count > threshold
    out.append(
        _bool_signal(
            signal_code="BUNDLE_OPPORTUNITY",
            category="product_strategy",
            severity="medium" if bundle_opportunity else "low",
            active=bundle_opportunity,
            signal_value=float(max_pair_count),
            threshold_value=float(threshold),
            context={"max_pair_count": max_pair_count, "bundle_pairs_count": len(bundle_pairs)},
        )
    )

    blank_sku_revenue = _to_float(adv.get("blank_sku_revenue"))
    data_hygiene_issue = blank_sku_revenue > 0
    out.append(
        _bool_signal(
            signal_code="DATA_HYGIENE_ISSUE",
            category="data_quality",
            severity="medium" if data_hygiene_issue else "low",
            active=data_hygiene_issue,
            signal_value=blank_sku_revenue,
            threshold_value=0.0,
            context={"blank_sku_revenue": blank_sku_revenue},
        )
    )

    monthly_revenue = adv.get("monthly_revenue", {})
    monthly_revenue_map = monthly_revenue if isinstance(monthly_revenue, dict) else {}
    max_abs_growth = _max_abs_mom_growth(monthly_revenue_map)
    unstable_growth = max_abs_growth > cfg["unstable_growth_abs_threshold"]
    out.append(
        _bool_signal(
            signal_code="UNSTABLE_GROWTH",
            category="growth_volatility",
            severity="medium" if unstable_growth else "low",
            active=unstable_growth,
            signal_value=max_abs_growth,
            threshold_value=cfg["unstable_growth_abs_threshold"],
            context={
                "max_abs_mom_revenue_growth": max_abs_growth,
                "months_observed": len(monthly_revenue_map),
            },
        )
    )

    return out

