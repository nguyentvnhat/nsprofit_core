"""Pure metrics orchestrator.

Input shape is intentionally loose (``list[dict]``) so callers can pass ORM dumps,
normalized dicts, or API payloads without coupling this layer to the database.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.services.metrics_engine.customer_metrics import compute_customer_metrics
from app.services.metrics_engine.order_metrics import (
    OrderMetricConfig,
    compute_order_metrics,
)
from app.services.metrics_engine.advanced_metrics import compute_advanced_metrics
from app.services.metrics_engine.product_metrics import compute_product_metrics
from app.services.metrics_engine.revenue_metrics import compute_revenue_metrics


@dataclass(frozen=True)
class MetricsEngineConfig:
    low_value_threshold: Decimal = Decimal("20")
    high_value_threshold: Decimal = Decimal("200")


def compute_metrics(
    *,
    orders: list[dict[str, Any]],
    order_items: list[dict[str, Any]],
    customers: list[dict[str, Any]],
    config: MetricsEngineConfig | None = None,
) -> dict[str, dict[str, Any]]:
    """Return one structured payload for signals/dashboard/storage layers."""
    cfg = config or MetricsEngineConfig()
    order_cfg = OrderMetricConfig(
        low_value_threshold=cfg.low_value_threshold,
        high_value_threshold=cfg.high_value_threshold,
    )
    revenue = compute_revenue_metrics(orders)
    order_quality = compute_order_metrics(orders, config=order_cfg)
    products = compute_product_metrics(orders, order_items)
    customer = compute_customer_metrics(orders, customers)
    advanced = compute_advanced_metrics(orders, order_items)
    return {
        "revenue": revenue,
        "orders": order_quality,
        "products": products,
        "customers": customer,
        "advanced": advanced,
    }


def run_all_metrics(
    *,
    orders: list[dict[str, Any]],
    order_items: list[dict[str, Any]],
    customers: list[dict[str, Any]],
    config: MetricsEngineConfig | None = None,
) -> dict[str, dict[str, Any]]:
    """Backward name kept; pure function signature only."""
    return compute_metrics(
        orders=orders,
        order_items=order_items,
        customers=customers,
        config=config,
    )


def metrics_as_flat_dict(metrics: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Flatten top-level scalar metrics for rule/signal engines."""
    out: dict[str, float] = {}
    for domain_values in metrics.values():
        for key, value in domain_values.items():
            if isinstance(value, (int, float, Decimal)):
                out[key] = float(value)
    return out


__all__ = ["MetricsEngineConfig", "compute_metrics", "metrics_as_flat_dict", "run_all_metrics"]
