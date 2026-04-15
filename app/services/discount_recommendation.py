"""
SKU-level basic discount recommendations from line-item economics.

Core idea
---------
This module builds lightweight discount recommendation rows at SKU level using
observed order-item economics.

Important constraint
--------------------
When COGS is not available in the source data, "margin" here is not true profit
margin. Instead, the module uses a retained-value proxy:

    pre-discount value ≈ net_line_revenue + line_discount_total
    retained share     = value left after discounts

Because unit cost is unknown, margin is expressed as a conservative uncertainty
band rather than a precise profitability number.

Output role in the pipeline
---------------------------
This module does NOT produce final campaign decisions by itself.
It produces SKU-level analytical rows that become input for:
- recommendation / promotion draft generation
- dashboard summarization
- UI-facing decision support

Design goals
------------
- deterministic
- replay-safe for historical CSV uploads
- simple enough to work without catalog enrichment
- compatible with both persisted DB orders and normalized in-memory payloads
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.models.order import Order
from app.repositories import OrderRepository

# Reference store-level discount ceiling used to estimate additional promotional headroom.
# This should stay aligned with campaign insight logic so both layers reason from a similar baseline.
_TARGET_DISCOUNT_SHARE = 0.15


def _line_discount_amount(li: Any) -> float:
    """
    Resolve the most reliable line-level discount amount from a line item object.

    Resolution order
    ----------------
    1. line_discount_amount
    2. total_discount_amount
    3. inferred discount from compare_at_price - unit_price

    Why this fallback exists
    ------------------------
    Source exports are not always consistent. Some rows may have explicit discount
    columns, while others only expose compare-at pricing. This helper centralizes
    the fallback logic so the rest of the module can work with one normalized
    discount value.

    Returns
    -------
    float
        Discount amount for the line item. Returns 0.0 when discount data cannot
        be resolved safely.
    """
    raw = getattr(li, "line_discount_amount", None)
    if raw is not None and float(raw or 0) != 0:
        return float(raw)

    tot = getattr(li, "total_discount_amount", None)
    if tot is not None and float(tot or 0) != 0:
        return float(tot)

    try:
        ca = float(getattr(li, "compare_at_price", None) or 0)
        up = float(getattr(li, "unit_price", None) or 0)
        qty = int(getattr(li, "quantity", None) or 0)
        if ca > 0 and up > 0 and ca > up:
            return (ca - up) * max(1, qty)
    except Exception:
        # Fail closed: if inference cannot be trusted, treat it as no discount
        # rather than raising and breaking the recommendation pipeline.
        pass

    return 0.0


def _snap_promo_pct(raw: float) -> float:
    """
    Snap a raw suggested promotional percentage into a merchant-friendly step.

    Why this exists
    ---------------
    Internal heuristics may produce awkward percentages, but merchants usually
    reason in simple promo tiers such as 5%, 10%, or 15%. This helper converts
    raw values into cleaner operational increments.

    Returns
    -------
    float
        One of the supported step values, or 0.0 when the raw suggestion is non-positive.
    """
    if raw <= 0:
        return 0.0

    for step in (15.0, 12.0, 10.0, 8.0, 5.0):
        if raw >= step - 0.01:
            return step

    return 5.0 if raw > 0 else 0.0


def _margin_band(retained_pct: float) -> tuple[float, float]:
    """
    Estimate a proxy "margin band" from retained value percentage.

    Important note
    --------------
    This is NOT true gross margin. It is a heuristic uncertainty band used when
    unit cost / COGS is missing.

    Intuition
    ---------
    - If the product retains a high share of pre-discount value, the likely
      margin room is stronger and the uncertainty band can be tighter.
    - If discounts are already deep, real profitability becomes more uncertain,
      so the band widens.

    Parameters
    ----------
    retained_pct:
        Percentage of value retained after discounts.

    Returns
    -------
    tuple[float, float]
        Lower and upper proxy margin bounds in percentage terms.
    """
    r = max(0.0, min(100.0, retained_pct))

    # Missing cost information makes true margin uncertain.
    # Use wider bands when discounting is already heavy.
    if r >= 75:
        low, high = r * 0.72, r * 0.98
    elif r >= 55:
        low, high = r * 0.62, r * 0.95
    else:
        low, high = r * 0.48, r * 0.88

    return (max(0.0, low), min(100.0, high))


def _after_extra_promo_retained(current_share: float, extra_pct: float) -> float:
    """
    Estimate retained value percentage after applying an additional promotion.

    Model
    -----
    The additional promotion is applied to the remaining discount headroom, not
    to the already-discounted portion.

    Parameters
    ----------
    current_share:
        Current discount share on a 0–1 scale.

    extra_pct:
        Additional promotion depth in percentage terms, e.g. 10.0 for 10%.

    Returns
    -------
    float
        Estimated retained value percentage after the additional promo.
    """
    extra = max(0.0, min(0.5, extra_pct / 100.0))
    head = max(0.0, 1.0 - current_share)
    new_share = min(1.0, current_share + head * extra)
    return max(0.0, (1.0 - new_share) * 100.0)


def build_discount_recommendation_rows_from_orders(orders: list[Order]) -> list[dict[str, Any]]:
    """
    Build SKU-level discount recommendation rows from persisted Order models.

    Scope
    -----
    This function works on already-persisted orders, which may come from:
    - upload-scoped analysis
    - store-scoped analysis

    What this function does
    -----------------------
    1. Aggregate order-item economics at SKU level
    2. Estimate current discount share and retained value
    3. Build proxy margin bands
    4. Estimate additional promotional headroom
    5. Add simple demand / recency signals
    6. Infer related SKUs from co-purchase behavior

    What this function does NOT do
    ------------------------------
    - It does not generate the final campaign object
    - It does not persist signals or insights
    - It does not use true cost accounting

    Returns
    -------
    list[dict[str, Any]]
        One analytical row per (sku, product_name), sorted by net revenue descending.
    """
    # Per-SKU accumulator structure:
    # [net_revenue_total, discount_total, quantity_total, order_count_approx,
    #  units_7d, units_30d, last_order_ordinal]
    acc: dict[tuple[str, str], list[float]] = {}

    # Use the max observed order date as the anchor date.
    # This keeps historical CSV replays stable and avoids depending on "today".
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

    # Aggregate order-item metrics per SKU.
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

        # Use order_name first, then external_order_id as a stable order identifier proxy.
        order_key = str(getattr(o, "order_name", "") or getattr(o, "external_order_id", "") or "")

        for li in o.items or []:
            sku = (li.sku or "UNKNOWN").strip() or "UNKNOWN"
            pname = (li.product_name or "").strip() or "Unnamed product"
            key = (sku, pname)

            # Prefer net_line_revenue; fall back to line_total if needed.
            net = float(li.net_line_revenue or li.line_total or 0)

            # Normalize discount amount using shared fallback logic.
            disc = _line_discount_amount(li)

            # Skip clearly invalid negative-value rows that have no discount explanation.
            if net < 0 and disc <= 0:
                continue

            # Approximate pre-discount value.
            pre = net + disc
            if pre <= 0:
                pre = max(net, 1e-6)

            qty = int(li.quantity or 0)

            if key not in acc:
                acc[key] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0]

            acc[key][0] += net
            acc[key][1] += disc
            acc[key][2] += qty

            if order_key:
                # Approximate per-SKU order count.
                # This intentionally avoids heavier unique-order tracking logic.
                # Confidence is later moderated by quantity and time-window activity.
                acc[key][3] += 1.0

            if oday is not None:
                if oday >= w7:
                    acc[key][4] += qty
                if oday >= w30:
                    acc[key][5] += qty
                acc[key][6] = max(acc[key][6], float(oday.toordinal()))

    # --- Related SKUs (co-purchase graph) ---
    # Infer "items bought together" from order-level SKU co-occurrence.
    # This is deterministic and requires no category or merchandising metadata.
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

        # Deduplicate SKUs per order so quantity-heavy orders do not over-weight co-purchase counts.
        uniq = sorted(set(skus_in_order))
        if len(uniq) < 2:
            continue

        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                a, b = uniq[i], uniq[j]
                pair_counts[(a, b)] = pair_counts.get((a, b), 0) + 1

    related_by_sku: dict[str, list[dict[str, Any]]] = {}
    for (a, b), ct in pair_counts.items():
        related_by_sku.setdefault(a, []).append(
            {"sku": b, "count": ct, "product_name": sku_name_by_sku.get(b, "")}
        )
        related_by_sku.setdefault(b, []).append(
            {"sku": a, "count": ct, "product_name": sku_name_by_sku.get(a, "")}
        )

    # Keep only the top 3 co-purchased SKUs per SKU for a compact response payload.
    for sku, lst in related_by_sku.items():
        lst.sort(key=lambda x: int(x.get("count") or 0), reverse=True)
        related_by_sku[sku] = lst[:3]

    rows: list[dict[str, Any]] = []

    # Convert accumulated SKU metrics into recommendation rows.
    for (sku, product_name), (net_tot, disc_tot, qty_tot, orders_ct, u7, u30, last_ord) in acc.items():
        pre_tot = net_tot + disc_tot
        if pre_tot <= 0:
            continue

        # Share of discount relative to pre-discount value.
        share = min(1.0, max(0.0, disc_tot / pre_tot))

        # Value retained after discounting.
        retained_pct = (1.0 - share) * 100.0

        # Approximate margin band from retained value.
        low_m, high_m = _margin_band(retained_pct)

        # Estimate how much additional promo depth is still "available"
        # relative to the target discount ceiling.
        headroom = max(0.0, _TARGET_DISCOUNT_SHARE - share)

        # Suggest additional promotional depth.
        # Stronger suggestions are allowed when the SKU is still close to full price.
        if share <= 0.03:
            raw_suggest = min(15.0, 10.0 + headroom * 80.0)
        elif share <= 0.12:
            raw_suggest = min(12.0, 8.0 + headroom * 60.0)
        elif share <= 0.22:
            raw_suggest = min(10.0, 5.0 + headroom * 40.0)
        else:
            raw_suggest = min(8.0, max(0.0, headroom * 35.0))

        suggested = _snap_promo_pct(raw_suggest)

        # When the SKU is already heavily discounted, cap further promotion conservatively.
        if share > 0.35:
            suggested = min(suggested, 5.0)

        # Estimate retained value and proxy margin after the additional promo.
        after = _after_extra_promo_retained(share, suggested)
        after_low, after_high = _margin_band(after)

        last_sale_days: int | None = None
        if last_ord >= 0:
            last_day = date.fromordinal(int(last_ord))
            last_sale_days = int((max_day - last_day).days)

        # Velocity bucket = simple demand / movement proxy.
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

        # Confidence is intentionally deterministic and conservative.
        # Higher volume and more recent activity increase confidence.
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

    # Rank rows by commercial significance first.
    rows.sort(key=lambda r: float(r["net_revenue"]), reverse=True)
    return rows


def build_discount_recommendation_rows(session: Session, upload_id: int) -> list[dict[str, Any]]:
    """
    Build discount recommendation rows for a persisted upload.

    This is the DB-backed convenience entry point used by upload-scoped analysis.
    It loads normalized order models, then delegates all analytical logic to the
    shared order-based builder.

    Returns
    -------
    list[dict[str, Any]]
        One row per SKU, sorted by net revenue descending.
    """
    orders = OrderRepository(session).list_orders_for_upload(
        upload_id,
        include_items=True,
        include_customer=False,
    )
    return build_discount_recommendation_rows_from_orders(orders)


def build_discount_recommendation_rows_from_normalized(
    orders: list[dict[str, Any]],
    order_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Build discount recommendation rows from normalized in-memory payloads.

    Why this exists
    ---------------
    Some flows need recommendation analysis before DB persistence, for example:
    - import preview flows
    - pipeline staging
    - temporary / transient processing

    Inputs
    ------
    Expected inputs are normalized dictionaries produced by:
        shopify_normalizer.normalize_shopify_data(...)

    Design note
    -----------
    This function intentionally mirrors the persisted-order logic closely so both
    DB-backed and in-memory flows behave consistently.
    """
    # Anchor day based on max observed order date for stable historical replays.
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

    # Build co-purchase relationships from normalized order items.
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
        _ = oname  # Keep explicit loop variable for readability / future debugging.
        uniq = sorted(sku_set)
        if len(uniq) < 2:
            continue

        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                a, b = uniq[i], uniq[j]
                pair_counts[(a, b)] = pair_counts.get((a, b), 0) + 1

    related_by_sku: dict[str, list[dict[str, Any]]] = {}
    for (a, b), ct in pair_counts.items():
        related_by_sku.setdefault(a, []).append(
            {"sku": b, "count": ct, "product_name": sku_name_by_sku.get(b, "")}
        )
        related_by_sku.setdefault(b, []).append(
            {"sku": a, "count": ct, "product_name": sku_name_by_sku.get(a, "")}
        )

    for sku, lst in related_by_sku.items():
        lst.sort(key=lambda x: int(x.get("count") or 0), reverse=True)
        related_by_sku[sku] = lst[:3]

    # Aggregate metrics per (sku, product_name).
    acc: dict[tuple[str, str], list[float]] = {}
    for it in order_items or []:
        sku = str(it.get("sku") or "UNKNOWN").strip() or "UNKNOWN"
        pname = str(it.get("product_name") or "").strip() or "Unnamed product"
        key = (sku, pname)

        qty = int(it.get("quantity") or 0)
        net = float(it.get("net_line_revenue") or it.get("line_total") or 0.0)

        # Prefer explicit discount values; otherwise infer from compare-at pricing.
        disc = float(it.get("line_discount_amount") or 0.0)
        if disc <= 0:
            try:
                ca = float(it.get("compare_at_price") or 0.0)
                up = float(it.get("unit_price") or 0.0)
                if ca > 0 and up > 0 and ca > up:
                    disc = (ca - up) * max(1, qty)
            except Exception:
                disc = 0.0

        # Skip clearly invalid negative rows with no discount explanation.
        if net < 0 and disc <= 0:
            continue

        pre = net + disc
        if pre <= 0:
            pre = max(net, 1e-6)

        if key not in acc:
            acc[key] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0]

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
    """
    Return the discount recommendation output as a pandas DataFrame.

    Why this wrapper exists
    -----------------------
    Some downstream consumers prefer a DataFrame representation for export,
    notebook inspection, or tabular processing.

    Behavior
    --------
    - Returns a DataFrame with stable columns even when there is no data.
    - Uses the DB-backed upload flow as the source.
    """
    data = build_discount_recommendation_rows(session, upload_id)

    if not data:
        # Return an empty DataFrame with a stable schema so downstream code
        # can rely on expected columns without adding special-case branching.
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