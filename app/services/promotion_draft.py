"""
Serializable promotion drafts — UI export today, Shopify Admin API tomorrow.

Level-1 MVP shape: simple % off + SKU targeting + duration. Keeps a stable
contract so portal or integration layers can consume the same objects.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# Bump when fields or semantics change (consumers / future API can branch).
PROMOTION_DRAFT_SCHEMA_VERSION = 3

# Human-readable label for analytics / future rule linkage.
SOURCE_HEURISTIC_V1 = "discount_recommendation_heuristic_v2"


@dataclass(frozen=True)
class PromotionDraft:
    """
    One actionable suggestion: "Giảm X% cho product (SKU) trong N ngày".

    Not tied to Shopify field names — mapping lives in ``integration.shopify_discounts``.
    """

    schema_version: int
    level: int  # roadmap level (1 = basic % MVP)
    source: str
    upload_id: int
    sku: str
    product_name: str
    suggested_discount_pct: float
    duration_days: int
    current_discount_pct: float
    net_revenue: float
    # Level-2 lite fields (optional enrichment, still deterministic).
    velocity_bucket: str = "unknown"  # slow/normal/fast/new_or_sparse
    units_7d: int = 0
    units_30d: int = 0
    days_since_last_sale: int | None = None
    confidence: str = "low"  # low/medium/high
    segment_policy: str = "all_customers"  # all_customers/new_customers/returning_customers
    rationale_codes: tuple[str, ...] = ()
    # Level-3 fields: promotion mix (still deterministic; executable later).
    campaign_type: str = "discount"  # discount/bundle/flash_sale
    campaign_template: dict[str, Any] | None = None
    store_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["rationale_codes"] = list(self.rationale_codes)
        return d


def _rationale_codes_for_row(row: dict[str, Any]) -> tuple[str, ...]:
    codes: list[str] = ["line_item_economics", "headroom_heuristic"]
    cur = float(row.get("current_discount_pct") or 0.0)
    if cur <= 3.0:
        codes.append("low_prior_discount")
    elif cur >= 25.0:
        codes.append("already_heavily_discounted_cap")
    vb = str(row.get("velocity_bucket") or "")
    if vb:
        codes.append(f"velocity_{vb}")
    conf = str(row.get("confidence") or "")
    if conf:
        codes.append(f"confidence_{conf}")
    store_codes = row.get("store_signal_codes")
    if isinstance(store_codes, list):
        for sc in store_codes:
            scs = str(sc or "").strip()
            if not scs:
                continue
            # Keep rationale compact: only include a curated subset for now.
            if scs in {"SKU_SLOW_MOVERS_HIGH"}:
                codes.append(f"store_signal_{scs}")
    return tuple(codes)


def _campaign_type_and_template_for_row(
    row: dict[str, Any],
    *,
    suggested_discount_pct: float,
    duration_days: int,
    level: int,
) -> tuple[str, dict[str, Any] | None, tuple[str, ...]]:
    """
    Level-3 (Promotion mix) heuristic.

    Returns (campaign_type, campaign_template, extra_rationale_codes).
    """
    if level < 3:
        return ("discount", None, ())

    vb = str(row.get("velocity_bucket") or "unknown").strip().lower()
    conf = str(row.get("confidence") or "low").strip().lower()
    cur = float(row.get("current_discount_pct") or 0.0)
    pct = float(suggested_discount_pct or 0.0)
    related = row.get("related_skus")
    related_list: list[dict[str, Any]] = related if isinstance(related, list) else []
    top_related = related_list[0] if related_list and isinstance(related_list[0], dict) else {}
    rel_sku = str(top_related.get("sku") or "").strip()
    rel_name = str(top_related.get("product_name") or "").strip()

    # Flash sale: show obvious "different" strategy for slow movers / sparse history.
    # Use a lower threshold so Level 3 visibly diverges from Level 2 in most datasets.
    if conf in {"high", "medium"} and pct >= 10.0 and vb in {"slow", "new_or_sparse"}:
        return (
            "flash_sale",
            {
                "type": "flash_sale",
                "discount_percent": round(pct, 2),
                "recommended_window_days": int(max(1, min(int(duration_days), 5))),
                "urgency": "limited_time",
            },
            ("campaign_type_flash_sale",),
        )

    # Bundle: default for fast/normal movers (AOV lift > deeper % off).
    # Even if pct is 12–15, cap the bundle tier at 10% to protect profit.
    if vb in {"fast", "normal"} and cur < 25.0:
        tier_pct = round(min(10.0, max(5.0, pct if pct > 0 else 8.0)), 2)
        return (
            "bundle",
            {
                "type": "bundle",
                "bundle_style": "cross_sku" if rel_sku else "buy_more_save_more",
                "primary_sku": str(row.get("sku") or ""),
                "related_skus": (
                    [{"sku": rel_sku, "product_name": rel_name}] if rel_sku else []
                ),
                "tiers": [{"min_qty": 2, "discount_percent": tier_pct}],
                "notes": (
                    "Cross-SKU bundle using co-purchase data."
                    if rel_sku
                    else "Default for fast/normal movers: lift AOV while keeping discount shallow."
                ),
            },
            ("campaign_type_bundle",),
        )

    # Default: simple discount (Level-2 style).
    return (
        "discount",
        {"type": "discount", "discount_percent": round(pct, 2)},
        ("campaign_type_discount",),
    )


def _segment_policy_for_row(row: dict[str, Any]) -> str:
    """
    Conservative segmentation (Level-2 lite).

    - Default: all customers
    - If suggested promo is deep, restrict to new customers first.
    - If SKU is already heavily discounted, avoid deepening for returning buyers.
    """
    pct = float(row.get("suggested_promo_pct") or 0.0)
    cur = float(row.get("current_discount_pct") or 0.0)
    if cur >= 25.0:
        return "new_customers"
    if pct >= 12.0:
        return "new_customers"
    return "all_customers"


def promotion_drafts_from_discount_rows(
    rows: list[dict[str, Any]],
    *,
    upload_id: int,
    store_id: int | None = None,
    duration_days: int = 3,
    level: int = 1,
    limit: int = 50,
) -> list[PromotionDraft]:
    """Build frozen drafts from :func:`build_discount_recommendation_rows` output."""
    out: list[PromotionDraft] = []
    for row in rows[: max(0, limit)]:
        pct = float(row.get("suggested_promo_pct") or 0.0)
        if pct <= 0:
            continue
        campaign_type, campaign_template, extra_codes = _campaign_type_and_template_for_row(
            row,
            suggested_discount_pct=pct,
            duration_days=int(duration_days),
            level=int(level),
        )
        base_codes = _rationale_codes_for_row(row)
        out.append(
            PromotionDraft(
                schema_version=PROMOTION_DRAFT_SCHEMA_VERSION,
                level=int(level) if int(level) >= 2 else 2,
                source=SOURCE_HEURISTIC_V1,
                upload_id=int(upload_id),
                sku=str(row.get("sku") or ""),
                product_name=str(row.get("product_name") or ""),
                suggested_discount_pct=round(pct, 2),
                duration_days=int(duration_days),
                current_discount_pct=float(row.get("current_discount_pct") or 0.0),
                net_revenue=float(row.get("net_revenue") or 0.0),
                velocity_bucket=str(row.get("velocity_bucket") or "unknown"),
                units_7d=int(row.get("units_7d") or 0),
                units_30d=int(row.get("units_30d") or 0),
                days_since_last_sale=(
                    int(row.get("days_since_last_sale"))
                    if row.get("days_since_last_sale") is not None
                    else None
                ),
                confidence=str(row.get("confidence") or "low"),
                segment_policy=_segment_policy_for_row(row),
                rationale_codes=tuple(list(base_codes) + list(extra_codes)),
                campaign_type=str(campaign_type),
                campaign_template=campaign_template,
                store_id=store_id,
            )
        )
    return out


def promotion_drafts_to_jsonable(drafts: list[PromotionDraft]) -> list[dict[str, Any]]:
    return [d.to_dict() for d in drafts]
