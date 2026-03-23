"""Shared signal types."""

from __future__ import annotations

from typing import Any, TypedDict


class Signal(TypedDict):
    signal_code: str
    category: str
    severity: str  # low / medium / high
    entity_type: str  # overall / product / customer / source
    entity_key: str | None
    signal_value: float
    threshold_value: float
    context: dict[str, Any]
