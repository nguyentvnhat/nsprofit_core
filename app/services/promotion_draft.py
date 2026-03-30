"""
Serializable promotion drafts — UI export today, Shopify Admin API tomorrow.

Level-1 MVP shape: simple % off + SKU targeting + duration. Keeps a stable
contract so portal or integration layers can consume the same objects.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# Bump when fields or semantics change (consumers / future API can branch).
PROMOTION_DRAFT_SCHEMA_VERSION = 1

# Human-readable label for analytics / future rule linkage.
SOURCE_HEURISTIC_V1 = "discount_recommendation_heuristic_v1"


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
    return tuple(codes)


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
                level=level,
                source=SOURCE_HEURISTIC_V1,
                upload_id=int(upload_id),
                sku=str(row.get("sku") or ""),
                product_name=str(row.get("product_name") or ""),
                suggested_discount_pct=round(pct, 2),
                duration_days=int(duration_days),
                current_discount_pct=float(row.get("current_discount_pct") or 0.0),
                net_revenue=float(row.get("net_revenue") or 0.0),
                rationale_codes=_rationale_codes_for_row(row),
            )
        )
    return out


def promotion_drafts_to_jsonable(drafts: list[PromotionDraft]) -> list[dict[str, Any]]:
    return [d.to_dict() for d in drafts]
