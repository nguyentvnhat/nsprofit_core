"""Pluggable pure signal detectors grouped by domain."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from app.services.signal_engine import (
    advanced_signals,
    customer_signals,
    discount_signals,
    product_signals,
    revenue_signals,
    risk_signals,
)
from app.services.signal_engine.types import Signal

SignalCollector = Callable[[dict[str, dict[str, Any]]], Sequence[Signal]]

SIGNAL_COLLECTORS: tuple[SignalCollector, ...] = (
    revenue_signals.collect,
    product_signals.collect,
    customer_signals.collect,
    risk_signals.collect,
    advanced_signals.collect,
    discount_signals.collect,
)


def run_all_signals(metrics: dict[str, dict[str, Any]]) -> list[Signal]:
    out: list[Signal] = []
    for fn in SIGNAL_COLLECTORS:
        out.extend(fn(metrics))
    return out


def signal_codes(signals: Sequence[Signal]) -> set[str]:
    return {str(s["signal_code"]) for s in signals}


__all__ = ["Signal", "run_all_signals", "signal_codes", "SIGNAL_COLLECTORS"]
