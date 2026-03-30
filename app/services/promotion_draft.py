"""
Serializable promotion drafts — UI export today, Shopify Admin API tomorrow.

Level-1 MVP shape: simple % off + SKU targeting + duration. Keeps a stable
contract so portal or integration layers can consume the same objects.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# Bump when fields or semantics change (consumers / future API can branch).
PROMOTION_DRAFT_SCHEMA_VERSION = 2

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
        out.append(
            PromotionDraft(
                schema_version=PROMOTION_DRAFT_SCHEMA_VERSION,
                level=level if level >= 2 else 2,
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
                rationale_codes=_rationale_codes_for_row(row),
            )
        )
    return out


def promotion_drafts_to_jsonable(drafts: list[PromotionDraft]) -> list[dict[str, Any]]:
    return [d.to_dict() for d in drafts]
