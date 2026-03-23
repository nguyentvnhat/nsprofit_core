"""Shared signal DTOs (keep free of collector imports)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SignalDraft:
    domain: str
    code: str
    severity: str
    payload: dict[str, object] = field(default_factory=dict)
