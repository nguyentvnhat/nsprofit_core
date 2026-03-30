"""
SKU-level basic discount recommendations from line-item economics.

Without COGS in the export, "margin" is modeled as a retained-value proxy:
pre-discount line value ≈ net_line_revenue + line_discount; retained share is
what remains after line discounts. Uncertainty bands widen when discounts are
already deep (aligned with :data:`_TARGET_DISCOUNT_RATE` in campaign insight).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.repositories import OrderRepository

# Align with campaign_insight_enricher._TARGET_DISCOUNT_RATE — store-level promo ceiling reference
_TARGET_DISCOUNT_SHARE = 0.15


def _snap_promo_pct(raw: float) -> float:
    """Round to a simple merchant-facing percentage (5 / 10 / 15)."""
    if raw <= 0:
        return 0.0
    for step in (15.0, 12.0, 10.0, 8.0, 5.0):
        if raw >= step - 0.01:
            return step
    return 5.0 if raw > 0 else 0.0


def _margin_band(retained_pct: float) -> tuple[float, float]:
    """
    Proxy band for "profit margin %" when COGS is unknown.

    Tightens when retained value is high (more room), widens when promo-heavy.
    """
    r = max(0.0, min(100.0, retained_pct))
    # Uncertainty from missing unit cost: wider when discounts already eat a lot of list
    if r >= 75:
        low, high = r * 0.72, r * 0.98
    elif r >= 55:
        low, high = r * 0.62, r * 0.95
    else:
        low, high = r * 0.48, r * 0.88
    return (max(0.0, low), min(100.0, high))


def _after_extra_promo_retained(current_share: float, extra_pct: float) -> float:
    """Retained share of list value if we add extra_pct off the remaining headroom (0–1 scale)."""
    extra = max(0.0, min(0.5, extra_pct / 100.0))
    head = max(0.0, 1.0 - current_share)
    new_share = min(1.0, current_share + head * extra)
    return max(0.0, (1.0 - new_share) * 100.0)


def build_discount_recommendation_rows(session: Session, upload_id: int) -> list[dict[str, Any]]:
    """
    One row per SKU with suggested simple promo % and margin proxy bands.

    Rows sorted by net line revenue descending.
    """
    orders = OrderRepository(session).list_orders_for_upload(
        upload_id,
        include_items=True,
        include_customer=False,
    )
    acc: dict[tuple[str, str], list[float]] = {}

    for o in orders:
        for li in o.items or []:
            sku = (li.sku or "UNKNOWN").strip() or "UNKNOWN"
            pname = (li.product_name or "").strip() or "Unnamed product"
            key = (sku, pname)
            net = float(li.net_line_revenue or li.line_total or 0)
            disc = float(li.line_discount_amount or 0)
            if net < 0 and disc <= 0:
                continue
            pre = net + disc
            if pre <= 0:
                pre = max(net, 1e-6)
            qty = int(li.quantity or 0)
            if key not in acc:
                acc[key] = [0.0, 0.0, 0.0]  # net, disc, qty
            acc[key][0] += net
            acc[key][1] += disc
            acc[key][2] += qty

    rows: list[dict[str, Any]] = []
    for (sku, product_name), (net_tot, disc_tot, qty_tot) in acc.items():
        pre_tot = net_tot + disc_tot
        if pre_tot <= 0:
            continue
        share = min(1.0, max(0.0, disc_tot / pre_tot))
        retained_pct = (1.0 - share) * 100.0
        low_m, high_m = _margin_band(retained_pct)

        headroom = max(0.0, _TARGET_DISCOUNT_SHARE - share)
        # Suggest a simple additional promo depth within headroom; stronger when catalog still full-price
        if share <= 0.03:
            raw_suggest = min(15.0, 10.0 + headroom * 80.0)
        elif share <= 0.12:
            raw_suggest = min(12.0, 8.0 + headroom * 60.0)
        elif share <= 0.22:
            raw_suggest = min(10.0, 5.0 + headroom * 40.0)
        else:
            raw_suggest = min(8.0, max(0.0, headroom * 35.0))

        suggested = _snap_promo_pct(raw_suggest)
        if share > 0.35:
            suggested = min(suggested, 5.0)

        after = _after_extra_promo_retained(share, suggested)
        after_low, after_high = _margin_band(after)

        rows.append(
            {
                "sku": sku,
                "product_name": product_name,
                "quantity": int(qty_tot),
                "net_revenue": round(net_tot, 2),
                "line_discount_total": round(disc_tot, 2),
                "current_discount_pct": round(share * 100.0, 2),
                "value_retained_pct": round(retained_pct, 2),
                "margin_proxy_low_pct": round(low_m, 1),
                "margin_proxy_high_pct": round(high_m, 1),
                "suggested_promo_pct": suggested,
                "after_promo_value_retained_pct": round(after, 2),
                "after_promo_margin_band_low_pct": round(after_low, 1),
                "after_promo_margin_band_high_pct": round(after_high, 1),
            }
        )

    rows.sort(key=lambda r: float(r["net_revenue"]), reverse=True)
    return rows


def get_discount_recommendation_dataframe(session: Session, upload_id: int) -> pd.DataFrame:
    data = build_discount_recommendation_rows(session, upload_id)
    if not data:
        return pd.DataFrame(
            columns=[
                "sku",
                "product_name",
                "quantity",
                "net_revenue",
                "line_discount_total",
                "current_discount_pct",
                "value_retained_pct",
                "margin_proxy_low_pct",
                "margin_proxy_high_pct",
                "suggested_promo_pct",
                "after_promo_value_retained_pct",
                "after_promo_margin_band_low_pct",
                "after_promo_margin_band_high_pct",
            ]
        )
    return pd.DataFrame(data)
