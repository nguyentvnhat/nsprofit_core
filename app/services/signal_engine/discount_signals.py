"""Discount/promotion signals derived from store-level discount metrics."""

from __future__ import annotations

from typing import Any

from app.services.signal_engine.types import Signal


def collect(metrics: dict[str, dict[str, Any]]) -> list[Signal]:
    disc = metrics.get("discount", {}) or {}
    slow_share = float(disc.get("slow_mover_sku_share") or 0.0)
    fast_share = float(disc.get("fast_mover_sku_share") or 0.0)
    active = float(disc.get("active_sku_count_30d") or 0.0)
    avg_days = float(disc.get("avg_days_since_last_sale_active_30d") or 0.0)

    out: list[Signal] = []
    if active >= 10 and slow_share >= 0.35:
        out.append(
            {
                "signal_code": "SKU_SLOW_MOVERS_HIGH",
                "severity": "medium",
                "entity_type": "overall",
                "entity_key": None,
                "signal_value": slow_share,
                "threshold_value": 0.35,
                "context": {
                    "active_sku_count_30d": active,
                    "slow_mover_sku_share": slow_share,
                    "fast_mover_sku_share": fast_share,
                    "avg_days_since_last_sale_active_30d": avg_days,
                },
            }
        )

    return out

