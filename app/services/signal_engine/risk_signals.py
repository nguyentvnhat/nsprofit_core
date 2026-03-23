"""Risk-domain signal rules (pure functions)."""

from __future__ import annotations

from typing import Any

from app.services.signal_engine.types import Signal

DEFAULTS: dict[str, float] = {
    "refund_rate_high_pct": 12.0,
    "free_shipping_rate_high_pct": 65.0,
}


def collect(metrics: dict[str, dict[str, Any]], config: dict[str, float] | None = None) -> list[Signal]:
    cfg = {**DEFAULTS, **(config or {})}
    revenue = metrics.get("revenue", {})
    orders = metrics.get("orders", {})
    out: list[Signal] = []

    gross = float(revenue.get("gross_revenue", 0.0))
    refunds = float(revenue.get("total_refunds", 0.0))
    refund_rate_pct = (refunds / gross) * 100.0 if gross > 0 else 0.0
    if refund_rate_pct >= cfg["refund_rate_high_pct"]:
        out.append(
            {
                "signal_code": "ELEVATED_REFUND_RATE",
                "category": "risk",
                "severity": "high",
                "entity_type": "overall",
                "entity_key": None,
                "signal_value": refund_rate_pct,
                "threshold_value": cfg["refund_rate_high_pct"],
                "context": {"refund_rate_pct": refund_rate_pct},
            }
        )

    free_shipping_rate_pct = float(orders.get("free_shipping_rate", 0.0)) * 100.0
    if free_shipping_rate_pct >= cfg["free_shipping_rate_high_pct"]:
        out.append(
            {
                "signal_code": "FREE_SHIPPING_HEAVY",
                "category": "operational_risk",
                "severity": "medium",
                "entity_type": "overall",
                "entity_key": None,
                "signal_value": free_shipping_rate_pct,
                "threshold_value": cfg["free_shipping_rate_high_pct"],
                "context": {"free_shipping_rate_pct": free_shipping_rate_pct},
            }
        )
    return out
