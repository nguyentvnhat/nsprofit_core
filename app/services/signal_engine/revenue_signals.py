"""Revenue-domain signal rules (pure functions)."""

from __future__ import annotations

from typing import Any

from app.services.signal_engine.types import Signal

# Defaults; override via future YAML `signals_thresholds` without embedding rules in Python UI.
DEFAULTS: dict[str, float] = {
    "high_discount_dependency_pct": 15.0,
    "low_aov_value": 20.0,
}


def collect(metrics: dict[str, dict[str, Any]], config: dict[str, float] | None = None) -> list[Signal]:
    cfg = {**DEFAULTS, **(config or {})}
    revenue = metrics.get("revenue", {})
    out: list[Signal] = []

    discount_ratio = float(revenue.get("discount_to_gross_ratio", 0.0)) * 100.0
    if discount_ratio >= cfg["high_discount_dependency_pct"]:
        out.append(
            {
                "signal_code": "HIGH_DISCOUNT_DEPENDENCY",
                "category": "pricing",
                "severity": "high",
                "entity_type": "overall",
                "entity_key": None,
                "signal_value": discount_ratio,
                "threshold_value": cfg["high_discount_dependency_pct"],
                "context": {
                    "discount_rate_pct": discount_ratio,
                    "total_orders": int(revenue.get("total_orders", 0)),
                },
            }
        )

    aov = float(revenue.get("aov", 0.0))
    if aov <= cfg["low_aov_value"] and int(revenue.get("total_orders", 0)) > 0:
        out.append(
            {
                "signal_code": "LOW_AOV_PRESSURE",
                "category": "revenue_quality",
                "severity": "medium",
                "entity_type": "overall",
                "entity_key": None,
                "signal_value": aov,
                "threshold_value": cfg["low_aov_value"],
                "context": {
                    "aov": aov,
                    "median_order_value": float(revenue.get("median_order_value", 0.0)),
                },
            }
        )
    return out
