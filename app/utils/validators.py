"""Lightweight validation helpers."""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_plausible_email(value: str | None) -> bool:
    if not value or not isinstance(value, str):
        return False
    return bool(_EMAIL_RE.match(value.strip()))
