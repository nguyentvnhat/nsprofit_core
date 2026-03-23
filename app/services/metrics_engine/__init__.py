"""
Modular metrics registry.

Add a collector returning ``MetricSnapshot`` rows and register it in ``METRIC_MODULES``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.metric_snapshot import MetricSnapshot
from app.services.metrics_engine import customer_metrics, order_metrics, product_metrics, revenue_metrics
from app.services.metrics_engine.snapshots import build_snapshot

MetricFn = Callable[[Session, int], Sequence[MetricSnapshot]]

METRIC_MODULES: tuple[MetricFn, ...] = (
    revenue_metrics.collect,
    order_metrics.collect,
    product_metrics.collect,
    customer_metrics.collect,
)


@dataclass
class MetricComputationResult:
    snapshots: list[MetricSnapshot]


def run_all_metrics(session: Session, upload_id: int) -> MetricComputationResult:
    snapshots: list[MetricSnapshot] = []
    for fn in METRIC_MODULES:
        snapshots.extend(fn(session, upload_id))
    return MetricComputationResult(snapshots=snapshots)


def metrics_as_flat_dict(snapshots: Sequence[MetricSnapshot]) -> dict[str, float]:
    """Overall / all_time metrics for YAML rule evaluation."""
    out: dict[str, float] = {}
    for s in snapshots:
        if (
            s.metric_scope == "overall"
            and s.period_type == "all_time"
            and s.dimension_1 is None
            and s.dimension_2 is None
        ):
            out[s.metric_code] = float(s.metric_value)
    return out


__all__ = [
    "METRIC_MODULES",
    "MetricComputationResult",
    "build_snapshot",
    "metrics_as_flat_dict",
    "run_all_metrics",
]
