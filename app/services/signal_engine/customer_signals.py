"""Customer behavior signals (repeat mix, concentration)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.services.signal_engine.types import SignalDraft

DEFAULT_REPEAT_RATIO_LOW = 0.08


def collect(
    session: Session,
    upload_id: int,
    metric_map: dict[str, float],
) -> Sequence[SignalDraft]:
    _ = session, upload_id
    repeat = float(metric_map.get("repeat_customer_ratio", 0.0))
    if repeat < DEFAULT_REPEAT_RATIO_LOW:
        return [
            SignalDraft(
                domain="customer",
                code="LOW_REPEAT_MIX",
                severity="info",
                payload={"repeat_customer_ratio": repeat, "threshold": DEFAULT_REPEAT_RATIO_LOW},
            )
        ]
    return []
