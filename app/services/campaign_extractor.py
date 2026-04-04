"""Campaign dimension extraction from normalized order dicts (no DB, no side effects)."""

from __future__ import annotations

import json
import re
from typing import Any

# Max stored key length after normalization (deterministic trim).
_MAX_CAMPAIGN_KEY_LEN = 128

_NOTES_PAYLOAD_KEY = "_np_campaign"


def _clean_token(raw: object | None) -> str:
    if raw is None:
        return ""
    s = str(raw).strip().lower()
    s = re.sub(r"\s+", " ", s)
    if not s:
        return ""
    if len(s) > _MAX_CAMPAIGN_KEY_LEN:
        s = s[:_MAX_CAMPAIGN_KEY_LEN].rstrip()
    return s


def extract_campaign_key(order: dict[str, Any]) -> str:
    """
    Derive a single campaign bucket key from order-level attribution fields.

    Priority: utm_campaign → landing_site → referrer → source_name → discount_code → ``unknown``.
    Never raises; missing values skip to the next source.
    """
    if not isinstance(order, dict):
        return "unknown"

    for key in (
        "utm_campaign",
        "landing_site",
        "referrer",
        "source_name",
        "discount_code",
    ):
        token = _clean_token(order.get(key))
        if token:
            return token
    return "unknown"


def group_orders_by_campaign(orders: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Partition orders by :func:`extract_campaign_key` (stable within list order)."""
    out: dict[str, list[dict[str, Any]]] = {}
    for o in orders:
        if not isinstance(o, dict):
            continue
        k = extract_campaign_key(o)
        out.setdefault(k, []).append(o)
    return out


def campaign_dims_to_notes_payload(order_dict: dict[str, Any]) -> str | None:
    """
    Serialize optional attribution dimensions into ``Order.notes`` JSON.

    Uses a namespaced key so future human ``notes`` usage can coexist.
    Returns ``None`` if no dimension is present.
    """
    if not isinstance(order_dict, dict):
        return None
    parts: dict[str, str] = {}
    for field in ("utm_campaign", "landing_site", "referrer", "discount_code"):
        v = order_dict.get(field)
        if v is None or str(v).strip() == "":
            continue
        s = str(v).strip()
        if len(s) > 512:
            s = s[:512].rstrip()
        parts[field] = s
    if not parts:
        return None
    return json.dumps({_NOTES_PAYLOAD_KEY: parts}, ensure_ascii=False)


def parse_campaign_notes(raw_notes: str | None) -> dict[str, str]:
    """Load attribution fields previously stored via :func:`campaign_dims_to_notes_payload`."""
    if not raw_notes or not str(raw_notes).strip():
        return {}
    try:
        data = json.loads(raw_notes)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    inner = data.get(_NOTES_PAYLOAD_KEY)
    if not isinstance(inner, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in inner.items():
        if v is None or str(v).strip() == "":
            continue
        out[str(k)] = str(v).strip()
    return out
