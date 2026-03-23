"""Timezone-aware date parsing for Shopify exports."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd


def parse_shopify_datetime(value: object, default_tz: str = "UTC") -> datetime | None:
    """Parse Shopify CSV datetime strings; returns timezone-aware UTC when possible."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=ZoneInfo(default_tz))
        return dt.astimezone(ZoneInfo("UTC"))
    text = str(value).strip()
    if not text:
        return None
    try:
        ts = pd.to_datetime(text, utc=True)
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except (ValueError, TypeError):
        return None


def to_naive_utc(dt: datetime | None) -> datetime | None:
    """Strip tz for MySQL DATETIME columns (store UTC as naive)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
