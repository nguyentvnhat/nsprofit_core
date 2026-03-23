"""Revenue domain signals (discount dependency, AOV stress — thresholds from metrics only here)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.services.signal_engine.types import SignalDraft

# Defaults; override via future YAML `signals_thresholds` without embedding rules in Python UI.
DEFAULT_DISCOUNT_RATIO_WARN = 0.15


def collect(
    session: Session,
    upload_id: int,
    metric_map: dict[str, float],
) -> Sequence[SignalDraft]:
    _ = session, upload_id
    ratio = float(metric_map.get("discount_to_gross_ratio", 0.0))
    if ratio >= DEFAULT_DISCOUNT_RATIO_WARN:
        return [
            SignalDraft(
                domain="revenue",
                code="HIGH_DISCOUNT_DEPENDENCY",
                severity="warning",
                payload={
                    "discount_to_gross_ratio": ratio,
                    "threshold": DEFAULT_DISCOUNT_RATIO_WARN,
                },
            )
        ]
    return []
