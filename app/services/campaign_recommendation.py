"""
Phase 1 (CSV input): Generate 3 promotion recommendations from Shopify orders export.

Scope: purely analytical recommendations (no Shopify API, no auto execution).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, Literal

from app.services.file_parser import parse_shopify_csv_with_result, parse_shopify_orders_csv
from app.services.shopify_normalizer import normalize_shopify_data

PromotionType = Literal["discount", "bundle", "bogo", "tiered_discount"]


@dataclass(frozen=True)
class ProductSalesStats:
    product: str
    sku: str | None
    units: int
    net_revenue: float
    orders_approx: int
    units_7d: int
    units_30d: int
    days_since_last_sale: int | None


def _as_date(v: object | None) -> date | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    # Most normalized values are ISO-ish already; keep deterministic parsing.
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def _to_int(v: object | None, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(float(str(v)))
    except (TypeError, ValueError):
        return default


def _to_float(v: object | None, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(str(v))
    except (TypeError, ValueError):
        return default


def _aggregate_product_stats(
    order_dicts: list[dict[str, Any]],
    item_dicts: list[dict[str, Any]],
) -> list[ProductSalesStats]:
    order_date_by_name: dict[str, date] = {}
    max_day: date | None = None
    for o in order_dicts:
        name = str(o.get("order_name") or "").strip()
        d = _as_date(o.get("order_date"))
        if not name or d is None:
            continue
        order_date_by_name[name] = d
        if max_day is None or d > max_day:
            max_day = d
    if max_day is None:
        max_day = date.today()
    w7 = max_day - timedelta(days=7)
    w30 = max_day - timedelta(days=30)

    # key -> [units, net, orders_approx, u7, u30, last_ord, sku]
    acc: dict[str, list[Any]] = {}
    for it in item_dicts:
        product = str(it.get("product_name") or "Unnamed product").strip() or "Unnamed product"
        sku = (str(it.get("sku")).strip() if it.get("sku") not in (None, "") else None) or None
        qty = max(0, _to_int(it.get("quantity"), 0))
        net = _to_float(it.get("net_line_revenue") or it.get("line_total"), 0.0)
        if qty == 0 and net == 0.0:
            continue

        if product not in acc:
            acc[product] = [0, 0.0, 0, 0, 0, None, sku]  # units, net, orders, u7, u30, last_day, sku
        acc[product][0] = int(acc[product][0]) + qty
        acc[product][1] = float(acc[product][1]) + net
        acc[product][2] = int(acc[product][2]) + 1  # approx: one per line-item row

        oname = str(it.get("order_name") or "").strip()
        od = order_date_by_name.get(oname)
        if od is not None:
            if od >= w7:
                acc[product][3] = int(acc[product][3]) + qty
            if od >= w30:
                acc[product][4] = int(acc[product][4]) + qty
            last = acc[product][5]
            if last is None or od > last:
                acc[product][5] = od

        # Keep a non-empty SKU if we saw one later.
        if acc[product][6] is None and sku:
            acc[product][6] = sku

    out: list[ProductSalesStats] = []
    for product, (units, net_rev, orders_approx, u7, u30, last_day, sku) in acc.items():
        days_since: int | None = None
        if isinstance(last_day, date):
            days_since = int((max_day - last_day).days)
        out.append(
            ProductSalesStats(
                product=product,
                sku=str(sku).strip() if sku else None,
                units=int(units),
                net_revenue=round(float(net_rev), 2),
                orders_approx=int(orders_approx),
                units_7d=int(u7),
                units_30d=int(u30),
                days_since_last_sale=days_since,
            )
        )

    out.sort(key=lambda s: s.net_revenue, reverse=True)
    return out


def _pick_top_products(stats: list[ProductSalesStats], limit: int = 3) -> list[ProductSalesStats]:
    # Top by net revenue with a mild unit floor to avoid one-off anomalies.
    ranked = sorted(stats, key=lambda s: (s.net_revenue, s.units), reverse=True)
    out: list[ProductSalesStats] = []
    for s in ranked:
        if s.units <= 0:
            continue
        out.append(s)
        if len(out) >= limit:
            break
    return out


def _pick_slow_movers(stats: list[ProductSalesStats], limit: int = 3) -> list[ProductSalesStats]:
    # Slow-moving heuristic: low recent units, older last sale, still has some history.
    def score(s: ProductSalesStats) -> tuple[int, int, float]:
        days = s.days_since_last_sale if s.days_since_last_sale is not None else 10_000
        return (days, -s.units_30d, s.net_revenue)

    ranked = sorted(stats, key=score, reverse=True)
    out: list[ProductSalesStats] = []
    for s in ranked:
        if s.units <= 0:
            continue
        if s.units_30d > 2 and (s.days_since_last_sale or 0) < 14:
            continue
        out.append(s)
        if len(out) >= limit:
            break
    return out


def _fmt_duration(days: int) -> str:
    if days <= 7:
        return "7 days"
    if days <= 14:
        return "14 days"
    if days <= 30:
        return "30 days"
    return f"{days} days"


def _expected_impact_text(
    *,
    product: ProductSalesStats,
    promo_type: PromotionType,
    duration_days: int,
) -> str:
    # Deterministic, conservative proxy: uplift % * baseline daily revenue.
    baseline_days = max(1, min(30, duration_days))
    baseline_daily = product.net_revenue / max(1, baseline_days)

    if promo_type == "discount":
        uplift_low, uplift_high = (0.08, 0.22) if (product.units_30d <= 2) else (0.05, 0.15)
    elif promo_type == "bundle":
        uplift_low, uplift_high = (0.06, 0.14)
    elif promo_type == "bogo":
        uplift_low, uplift_high = (0.10, 0.25)
    else:  # tiered_discount
        uplift_low, uplift_high = (0.05, 0.12)

    low = baseline_daily * duration_days * uplift_low
    high = baseline_daily * duration_days * uplift_high

    # Use a human-friendly narrative (currency unknown at this layer; keep generic).
    return (
        f"Expected lift: +{uplift_low*100:.0f}% to +{uplift_high*100:.0f}% vs baseline for this product "
        f"over {_fmt_duration(duration_days)} (proxy impact: +{low:,.0f} to +{high:,.0f} net revenue units)."
    )


def generate_3_promotion_recommendations_from_orders_csv(
    order_csv: str | Path | BinaryIO | bytes | list[dict[str, Any]],
    *,
    duration_days: int = 14,
) -> list[dict[str, Any]]:
    """
    Read Shopify orders CSV data and generate exactly 3 product-level promo recommendations.

    Input can be:
    - path (str/Path)
    - binary stream (BinaryIO)
    - raw bytes
    - already-parsed canonical rows (list of dict)

    Output schema (3 items):
    - product
    - promotion_type
    - duration
    - expected_impact
    """
    rows: list[dict[str, Any]]
    if isinstance(order_csv, list):
        rows = order_csv
    elif isinstance(order_csv, (str, Path)):
        parsed = parse_shopify_csv_with_result(Path(order_csv))
        rows = parsed.rows
    elif isinstance(order_csv, (bytes, bytearray)):
        parsed = parse_shopify_orders_csv(BytesIO(bytes(order_csv)))
        rows = parsed.rows
    else:
        parsed = parse_shopify_orders_csv(order_csv)
        rows = parsed.rows

    order_dicts, item_dicts, _customers = normalize_shopify_data(rows)
    stats = _aggregate_product_stats(order_dicts, item_dicts)
    if not stats:
        return []

    top = _pick_top_products(stats, limit=3)
    slow = _pick_slow_movers(stats, limit=3)

    # Build 3 recommendations with simple diversification:
    # 1) Slow mover discount (clear stock)
    # 2) Top product tiered discount (protect margin vs sitewide)
    # 3) Bundle top #1 with top #2 when possible, else BOGO on top #1
    picks: list[dict[str, Any]] = []

    slow_pick = slow[0] if slow else None
    if slow_pick:
        picks.append(
            {
                "product": slow_pick.product,
                "promotion_type": "discount",
                "duration": _fmt_duration(duration_days),
                "expected_impact": _expected_impact_text(
                    product=slow_pick,
                    promo_type="discount",
                    duration_days=duration_days,
                ),
            }
        )

    top1 = top[0] if top else stats[0]
    picks.append(
        {
            "product": top1.product,
            "promotion_type": "tiered_discount",
            "duration": _fmt_duration(duration_days),
            "expected_impact": _expected_impact_text(
                product=top1,
                promo_type="tiered_discount",
                duration_days=duration_days,
            ),
        }
    )

    top2 = top[1] if len(top) > 1 else None
    if top2 and top2.product != top1.product:
        picks.append(
            {
                "product": f"{top1.product} + {top2.product}",
                "promotion_type": "bundle",
                "duration": _fmt_duration(duration_days),
                "expected_impact": (
                    "Expected lift: +6% to +14% on combined basket conversion for these products "
                    f"over {_fmt_duration(duration_days)} (proxy; strongest when featured together in ads + cart upsell)."
                ),
            }
        )
    else:
        picks.append(
            {
                "product": top1.product,
                "promotion_type": "bogo",
                "duration": _fmt_duration(duration_days),
                "expected_impact": _expected_impact_text(
                    product=top1,
                    promo_type="bogo",
                    duration_days=duration_days,
                ),
            }
        )

    # Ensure exactly 3 (and de-duplicate identical dicts defensively).
    uniq: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for r in picks:
        key = (str(r.get("product") or ""), str(r.get("promotion_type") or ""))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
        if len(uniq) >= 3:
            break

    # Backfill if slow_pick missing or duplicates occurred.
    if len(uniq) < 3:
        for s in stats:
            cand = {
                "product": s.product,
                "promotion_type": "discount",
                "duration": _fmt_duration(duration_days),
                "expected_impact": _expected_impact_text(
                    product=s,
                    promo_type="discount",
                    duration_days=duration_days,
                ),
            }
            key = (cand["product"], cand["promotion_type"])
            if key in seen:
                continue
            uniq.append(cand)
            seen.add(key)
            if len(uniq) >= 3:
                break

    return uniq[:3]

