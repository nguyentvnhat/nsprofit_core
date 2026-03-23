"""Decimal-safe money helpers for CSV numerics."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import pandas as pd


def to_decimal(value: object) -> Decimal | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def to_float(value: object) -> float | None:
    d = to_decimal(value)
    return float(d) if d is not None else None
