"""Factory for ``MetricSnapshot`` rows (keeps metric modules free of circular imports)."""

from __future__ import annotations

from decimal import Decimal

from app.models.metric_snapshot import MetricSnapshot


def build_snapshot(
    upload_id: int,
    metric_code: str,
    value: float | Decimal,
    *,
    metric_scope: str = "overall",
    dimension_1: str | None = None,
    dimension_2: str | None = None,
    period_type: str = "all_time",
    period_value: str | None = None,
) -> MetricSnapshot:
    v = value if isinstance(value, Decimal) else Decimal(str(value))
    return MetricSnapshot(
        upload_id=upload_id,
        metric_code=metric_code,
        metric_scope=metric_scope,
        dimension_1=dimension_1,
        dimension_2=dimension_2,
        period_type=period_type,
        period_value=period_value,
        metric_value=v,
    )
