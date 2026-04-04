"""
SKU-level basic discount recommendations from line-item economics.

Without COGS in the export, "margin" is modeled as a retained-value proxy:
pre-discount line value ≈ net_line_revenue + line_discount; retained share is
what remains after line discounts. Uncertainty bands widen when discounts are
already deep (aligned with :data:`_TARGET_DISCOUNT_RATE` in campaign insight).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
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
    # Per-SKU accumulator:
    # [net, discount, qty, orders_count, units_7d, units_30d, last_order_ordinal]
    acc: dict[tuple[str, str], list[float]] = {}

    # Use max observed order date as anchor (stable for historical CSV replays).
    max_day: date | None = None
    for o in orders:
        odt = getattr(o, "order_date", None)
        if odt is None:
            continue
        if isinstance(odt, datetime):
            d = odt.date()
        else:
            try:
                d = date.fromisoformat(str(odt)[:10])
            except Exception:
                continue
        if max_day is None or d > max_day:
            max_day = d
    if max_day is None:
        max_day = date.today()
    w7 = max_day - timedelta(days=7)
    w30 = max_day - timedelta(days=30)

    for o in orders:
        odt = getattr(o, "order_date", None)
        oday: date | None = None
        if odt is not None:
            if isinstance(odt, datetime):
                oday = odt.date()
            else:
                try:
                    oday = date.fromisoformat(str(odt)[:10])
                except Exception:
                    oday = None
        order_key = str(getattr(o, "order_name", "") or getattr(o, "external_order_id", "") or "")
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
                acc[key] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0]  # net, disc, qty, orders, u7, u30, last_day_ord
            acc[key][0] += net
            acc[key][1] += disc
            acc[key][2] += qty
            if order_key:
                # approximate per-SKU order count: count unique order key by storing hash in a cheap way is heavy;
                # instead increment once per line item but clamp later via qty-based confidence.
                acc[key][3] += 1.0
            if oday is not None:
                if oday >= w7:
                    acc[key][4] += qty
                if oday >= w30:
                    acc[key][5] += qty
                acc[key][6] = max(acc[key][6], float(oday.toordinal()))

    # --- Related SKUs (co-purchase) ---
    # Build a simple co-occurrence graph: "items bought together in the same order".
    # This is deterministic and works without catalog/category data.
    sku_name_by_sku: dict[str, str] = {}
    for (sku, product_name) in acc.keys():
        if sku and product_name and sku not in sku_name_by_sku:
            sku_name_by_sku[sku] = product_name

    pair_counts: dict[tuple[str, str], int] = {}
    for o in orders:
        skus_in_order: list[str] = []
        for li in o.items or []:
            sku = (li.sku or "UNKNOWN").strip() or "UNKNOWN"
            if not sku or sku == "UNKNOWN":
                continue
            skus_in_order.append(sku)
        # Unique SKUs per order to avoid overweighting quantity lines
        uniq = sorted(set(skus_in_order))
        if len(uniq) < 2:
            continue
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                a, b = uniq[i], uniq[j]
                pair_counts[(a, b)] = pair_counts.get((a, b), 0) + 1

    related_by_sku: dict[str, list[dict[str, Any]]] = {}
    for (a, b), ct in pair_counts.items():
        related_by_sku.setdefault(a, []).append({"sku": b, "count": ct, "product_name": sku_name_by_sku.get(b, "")})
        related_by_sku.setdefault(b, []).append({"sku": a, "count": ct, "product_name": sku_name_by_sku.get(a, "")})
    for sku, lst in related_by_sku.items():
        lst.sort(key=lambda x: int(x.get("count") or 0), reverse=True)
        related_by_sku[sku] = lst[:3]

    rows: list[dict[str, Any]] = []
    for (sku, product_name), (net_tot, disc_tot, qty_tot, orders_ct, u7, u30, last_ord) in acc.items():
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

        last_sale_days: int | None = None
        if last_ord >= 0:
            last_day = date.fromordinal(int(last_ord))
            last_sale_days = int((max_day - last_day).days)

        # Velocity bucket (proxy inventory / demand).
        u7i, u30i = int(u7), int(u30)
        if u30i <= 0 and qty_tot > 0:
            velocity_bucket = "new_or_sparse"
        elif u7i <= 0 and u30i > 0:
            velocity_bucket = "slow"
        elif u30i > 0 and (u7i / max(1, u30i)) < 0.15:
            velocity_bucket = "slow"
        elif u7i >= 5:
            velocity_bucket = "fast"
        else:
            velocity_bucket = "normal"

        # Confidence is deterministic and conservative: more line volume and more recent sales => higher.
        if qty_tot >= 40 or u30i >= 25:
            confidence = "high"
        elif qty_tot >= 12 or u30i >= 8:
            confidence = "medium"
        else:
            confidence = "low"

        rows.append(
            {
                "sku": sku,
                "product_name": product_name,
                "quantity": int(qty_tot),
                "orders_approx": int(orders_ct),
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
                "units_7d": u7i,
                "units_30d": u30i,
                "days_since_last_sale": last_sale_days,
                "velocity_bucket": velocity_bucket,
                "confidence": confidence,
                "related_skus": related_by_sku.get(sku, []),
            }
        )

    rows.sort(key=lambda r: float(r["net_revenue"]), reverse=True)
    return rows


def build_discount_recommendation_rows_from_normalized(
    orders: list[dict[str, Any]],
    order_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Build discount recommendation rows without DB persistence.

    Inputs are the normalized dict outputs from `shopify_normalizer.normalize_shopify_data(...)`.
    """
    # Anchor day based on max observed order date for stable replays.
    max_day: date | None = None
    order_day_by_name: dict[str, date] = {}
    for o in orders or []:
        odt = o.get("order_date") or o.get("created_at") or o.get("processed_at")
        d: date | None = None
        if isinstance(odt, datetime):
            d = odt.date()
        elif odt is not None:
            try:
                d = date.fromisoformat(str(odt)[:10])
            except Exception:
                d = None
        if d is None:
            continue
        name = str(o.get("order_name") or o.get("external_order_id") or "").strip()
        if name:
            order_day_by_name[name] = d
        if max_day is None or d > max_day:
            max_day = d
    if max_day is None:
        max_day = date.today()
    w7 = max_day - timedelta(days=7)
    w30 = max_day - timedelta(days=30)

    # Related SKU co-purchase counts by order
    skus_by_order: dict[str, set[str]] = {}
    sku_name_by_sku: dict[str, str] = {}
    for it in order_items or []:
        oname = str(it.get("order_name") or "").strip()
        sku = str(it.get("sku") or "").strip()
        if not oname or not sku:
            continue
        skus_by_order.setdefault(oname, set()).add(sku)
        pname = str(it.get("product_name") or "").strip()
        if pname and sku not in sku_name_by_sku:
            sku_name_by_sku[sku] = pname

    pair_counts: dict[tuple[str, str], int] = {}
    for oname, sku_set in skus_by_order.items():
        _ = oname
        uniq = sorted(sku_set)
        if len(uniq) < 2:
            continue
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                a, b = uniq[i], uniq[j]
                pair_counts[(a, b)] = pair_counts.get((a, b), 0) + 1

    related_by_sku: dict[str, list[dict[str, Any]]] = {}
    for (a, b), ct in pair_counts.items():
        related_by_sku.setdefault(a, []).append({"sku": b, "count": ct, "product_name": sku_name_by_sku.get(b, "")})
        related_by_sku.setdefault(b, []).append({"sku": a, "count": ct, "product_name": sku_name_by_sku.get(a, "")})
    for sku, lst in related_by_sku.items():
        lst.sort(key=lambda x: int(x.get("count") or 0), reverse=True)
        related_by_sku[sku] = lst[:3]

    # Aggregate per (sku, product_name)
    acc: dict[tuple[str, str], list[float]] = {}
    for it in order_items or []:
        sku = str(it.get("sku") or "UNKNOWN").strip() or "UNKNOWN"
        pname = str(it.get("product_name") or "").strip() or "Unnamed product"
        key = (sku, pname)
        qty = int(it.get("quantity") or 0)
        net = float(it.get("net_line_revenue") or it.get("line_total") or 0.0)

        # Discount proxy: prefer explicit line_discount_amount; otherwise infer from compare_at - unit_price.
        disc = float(it.get("line_discount_amount") or 0.0)
        if disc <= 0:
            try:
                ca = float(it.get("compare_at_price") or 0.0)
                up = float(it.get("unit_price") or 0.0)
                if ca > 0 and up > 0 and ca > up:
                    disc = (ca - up) * max(1, qty)
            except Exception:
                disc = 0.0

        if net < 0 and disc <= 0:
            continue
        pre = net + disc
        if pre <= 0:
            pre = max(net, 1e-6)

        if key not in acc:
            acc[key] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0]  # net, disc, qty, orders, u7, u30, last_day_ord
        acc[key][0] += net
        acc[key][1] += disc
        acc[key][2] += qty
        acc[key][3] += 1.0

        oname = str(it.get("order_name") or "").strip()
        oday = order_day_by_name.get(oname)
        if oday is not None:
            if oday >= w7:
                acc[key][4] += qty
            if oday >= w30:
                acc[key][5] += qty
            acc[key][6] = max(acc[key][6], float(oday.toordinal()))

    rows: list[dict[str, Any]] = []
    for (sku, product_name), (net_tot, disc_tot, qty_tot, orders_ct, u7, u30, last_ord) in acc.items():
        pre_tot = net_tot + disc_tot
        if pre_tot <= 0:
            continue
        share = min(1.0, max(0.0, disc_tot / pre_tot))
        retained_pct = (1.0 - share) * 100.0
        low_m, high_m = _margin_band(retained_pct)

        headroom = max(0.0, _TARGET_DISCOUNT_SHARE - share)
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

        last_sale_days: int | None = None
        if last_ord >= 0:
            last_day = date.fromordinal(int(last_ord))
            last_sale_days = int((max_day - last_day).days)

        u7i, u30i = int(u7), int(u30)
        if u30i <= 0 and qty_tot > 0:
            velocity_bucket = "new_or_sparse"
        elif u7i <= 0 and u30i > 0:
            velocity_bucket = "slow"
        elif u30i > 0 and (u7i / max(1, u30i)) < 0.15:
            velocity_bucket = "slow"
        elif u7i >= 5:
            velocity_bucket = "fast"
        else:
            velocity_bucket = "normal"

        if qty_tot >= 40 or u30i >= 25:
            confidence = "high"
        elif qty_tot >= 12 or u30i >= 8:
            confidence = "medium"
        else:
            confidence = "low"

        rows.append(
            {
                "sku": sku,
                "product_name": product_name,
                "quantity": int(qty_tot),
                "orders_approx": int(orders_ct),
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
                "units_7d": u7i,
                "units_30d": u30i,
                "days_since_last_sale": last_sale_days,
                "velocity_bucket": velocity_bucket,
                "confidence": confidence,
                "related_skus": related_by_sku.get(sku, []),
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
                "orders_approx",
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
                "units_7d",
                "units_30d",
                "days_since_last_sale",
                "velocity_bucket",
                "confidence",
            ]
        )
    return pd.DataFrame(data)
