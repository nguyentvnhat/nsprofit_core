"""Customer-domain signal rules (pure functions)."""

from __future__ import annotations

from typing import Any

from app.services.signal_engine.types import Signal

DEFAULTS: dict[str, float] = {
    "repeat_customer_rate_low_pct": 15.0,
    "top_customer_revenue_share_high_pct": 30.0,
}


def collect(metrics: dict[str, dict[str, Any]], config: dict[str, float] | None = None) -> list[Signal]:
    cfg = {**DEFAULTS, **(config or {})}
    customer = metrics.get("customers", {})
    out: list[Signal] = []

    repeat_rate_pct = float(customer.get("repeat_customer_rate", 0.0)) * 100.0
    if repeat_rate_pct < cfg["repeat_customer_rate_low_pct"]:
        out.append(
            {
                "signal_code": "LOW_REPEAT_MIX",
                "category": "retention",
                "severity": "high",
                "entity_type": "overall",
                "entity_key": None,
                "signal_value": repeat_rate_pct,
                "threshold_value": cfg["repeat_customer_rate_low_pct"],
                "context": {
                    "repeat_customer_rate_pct": repeat_rate_pct,
                    "repeat_customer_count": int(customer.get("repeat_customer_count", 0)),
                    "total_customers": int(customer.get("total_customers", 0)),
                },
            }
        )

    top_share_pct = float(customer.get("top_customer_revenue_share", 0.0)) * 100.0
    if top_share_pct >= cfg["top_customer_revenue_share_high_pct"]:
        out.append(
            {
                "signal_code": "TOP_CUSTOMER_CONCENTRATION_HIGH",
                "category": "customer_concentration",
                "severity": "medium",
                "entity_type": "overall",
                "entity_key": None,
                "signal_value": top_share_pct,
                "threshold_value": cfg["top_customer_revenue_share_high_pct"],
                "context": {"top_customer_revenue_share_pct": top_share_pct},
            }
        )
    return out
