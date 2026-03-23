"""Product-domain signal rules (pure functions)."""

from __future__ import annotations

from typing import Any

from app.services.signal_engine.types import Signal

DEFAULTS: dict[str, float] = {
    "top_3_sku_share_high_pct": 60.0,
    "product_discount_rate_high_pct": 20.0,
}


def collect(metrics: dict[str, dict[str, Any]], config: dict[str, float] | None = None) -> list[Signal]:
    cfg = {**DEFAULTS, **(config or {})}
    products = metrics.get("products", {})
    out: list[Signal] = []

    top3_share_pct = float(products.get("top_3_sku_share", 0.0)) * 100.0
    if top3_share_pct >= cfg["top_3_sku_share_high_pct"]:
        out.append(
            {
                "signal_code": "SKU_QUANTITY_CONCENTRATION",
                "category": "product_mix",
                "severity": "high",
                "entity_type": "overall",
                "entity_key": None,
                "signal_value": top3_share_pct,
                "threshold_value": cfg["top_3_sku_share_high_pct"],
                "context": {"top_3_sku_share_pct": top3_share_pct},
            }
        )

    product_discount_rate_pct = float(products.get("product_discount_rate", 0.0)) * 100.0
    if product_discount_rate_pct >= cfg["product_discount_rate_high_pct"]:
        out.append(
            {
                "signal_code": "PRODUCT_DISCOUNT_RATE_HIGH",
                "category": "pricing",
                "severity": "medium",
                "entity_type": "overall",
                "entity_key": None,
                "signal_value": product_discount_rate_pct,
                "threshold_value": cfg["product_discount_rate_high_pct"],
                "context": {"product_discount_rate_pct": product_discount_rate_pct},
            }
        )
    return out
