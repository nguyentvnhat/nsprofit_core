"""
Modular metrics registry.

Add a new module (e.g. `shipping_metrics.py`), implement `register_metrics`,
and append to `METRIC_MODULES` below.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.metric_snapshot import MetricSnapshot
from app.services.metrics_engine import customer_metrics, order_metrics, product_metrics, revenue_metrics

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
    """Single-dimension metrics for rule evaluation (extend for keyed dimensions later)."""
    out: dict[str, float] = {}
    for s in snapshots:
        if s.dimension_key is None and s.value_numeric is not None:
            out[s.metric_key] = float(s.value_numeric)
    return out
