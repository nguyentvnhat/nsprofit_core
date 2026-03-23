"""
Pluggable signal detectors grouped by domain.

Add a collector function with signature `(Session, int, dict[str, float]) -> Sequence[SignalDraft]`
and register it in `SIGNAL_COLLECTORS`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from sqlalchemy.orm import Session

from app.services.signal_engine import customer_signals, product_signals, revenue_signals, risk_signals
from app.services.signal_engine.types import SignalDraft

SignalCollector = Callable[[Session, int, dict[str, float]], Sequence[SignalDraft]]

SIGNAL_COLLECTORS: tuple[SignalCollector, ...] = (
    revenue_signals.collect,
    product_signals.collect,
    customer_signals.collect,
    risk_signals.collect,
)


def run_all_signals(
    session: Session,
    upload_id: int,
    metric_map: dict[str, float],
) -> list[SignalDraft]:
    out: list[SignalDraft] = []
    for fn in SIGNAL_COLLECTORS:
        out.extend(fn(session, upload_id, metric_map))
    return out


def signal_codes(signals: Sequence[SignalDraft]) -> set[str]:
    return {s.code for s in signals}


__all__ = ["SignalDraft", "run_all_signals", "signal_codes", "SIGNAL_COLLECTORS"]
