"""
Upload-driven guardrail copy for /api/discount — not static marketing text.

Uses the same row dicts as ``build_discount_recommendation_rows_from_normalized``.
"""

from __future__ import annotations

from typing import Any

from app.services.discount_recommendation import _TARGET_DISCOUNT_SHARE


def build_guardrails_from_upload_rows(
    rows: list[dict[str, Any]],
    *,
    level: int,
    duration_days: int,
) -> dict[str, Any]:
    """
    Build guardrails block aligned with actual CSV line-item aggregates.

    ``rows`` should be the full list returned by ``build_discount_recommendation_rows_from_normalized``
    (before applying ``limit``), so counts match the engine input.
    """
    lvl = int(level or 3)
    dur = int(duration_days or 3)
    n = len(rows)

    if n == 0:
        return {
            "title": "Guardrails (no SKU rows)",
            "duration_days": dur,
            "engine_level": lvl,
            "items": [
                {
                    "code": "insufficient_lines",
                    "label": "No billable line items after parsing — try a larger Shopify orders export or check column mapping.",
                },
            ],
            "stats": {"sku_rows": 0},
        }

    low = sum(1 for r in rows if str(r.get("confidence") or "").lower().strip() == "low")
    med = sum(1 for r in rows if str(r.get("confidence") or "").lower().strip() == "medium")
    high = sum(1 for r in rows if str(r.get("confidence") or "").lower().strip() == "high")
    heavy = sum(1 for r in rows if float(r.get("current_discount_pct") or 0.0) >= 25.0)

    suggested_pcts = [float(r.get("suggested_promo_pct") or 0.0) for r in rows]
    max_s = max(suggested_pcts) if suggested_pcts else 0.0
    mean_s = sum(suggested_pcts) / len(suggested_pcts)

    current_pcts = [float(r.get("current_discount_pct") or 0.0) for r in rows]
    mean_cur = sum(current_pcts) / len(current_pcts)

    slow_v = sum(1 for r in rows if str(r.get("velocity_bucket") or "").lower().strip() == "slow")
    new_sparse = sum(
        1 for r in rows if str(r.get("velocity_bucket") or "").lower().strip() == "new_or_sparse"
    )

    cap_pct = round(_TARGET_DISCOUNT_SHARE * 100.0, 0)

    items: list[dict[str, str]] = [
        {
            "code": "cap_extra_discount",
            "label": (
                f"Extra discount steps in this run use 5/8/10/12/15% snaps; "
                f"max suggested extra here is {max_s:.1f}% (mean {mean_s:.1f}%) across {n} SKUs. "
                f"Heuristic headroom targets ~{cap_pct:.0f}% incremental discount share vs list."
            ),
        },
        {
            "code": "heavy_discount_new_customers",
            "label": (
                f"{heavy} of {n} SKUs are already ≥25% off in this file — "
                f"prefer new-customer-only or skip for those lines when policy allows."
                if heavy
                else (
                    f"No SKUs in this upload are already ≥25% off (mean current line discount "
                    f"{mean_cur:.1f}%) — still avoid stacking with order-wide promos."
                )
            ),
        },
        {
            "code": "low_confidence_shorter",
            "label": (
                f"Confidence split from order volume: high {high}, medium {med}, low {low}. "
                f"Low-confidence SKUs ({low}): shorten runs (this request uses {dur} day(s)) "
                f"or upload more weeks of orders."
            ),
        },
        {
            "code": "scope_per_product",
            "label": (
                f"All {n} draft lines are per-SKU (no site-wide blanket promos). "
                f"Slow/new_or_sparse velocity: {slow_v + new_sparse} SKUs — review cadence before scaling."
            ),
        },
    ]

    if lvl < 3:
        items.insert(
            0,
            {
                "code": "engine_level_note",
                "label": (
                    f"Engine level {lvl}: discount-only suggestions (no bundle/flash mix). "
                    f"Use level 3 for promotion mix when appropriate."
                ),
            },
        )

    return {
        "title": "Guardrails (from this upload)",
        "duration_days": dur,
        "engine_level": lvl,
        "items": items,
        "stats": {
            "sku_rows": n,
            "confidence": {"low": low, "medium": med, "high": high},
            "already_ge_25pct_skus": heavy,
            "max_suggested_extra_pct": round(max_s, 2),
            "mean_suggested_extra_pct": round(mean_s, 2),
            "mean_current_discount_pct": round(mean_cur, 2),
            "velocity_slow_or_sparse": slow_v + new_sparse,
        },
    }
