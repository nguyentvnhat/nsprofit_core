"""
Shopify discount creation — placeholder for Admin API / GraphQL.

When :attr:`Settings.shopify_discount_integration_enabled` is true, callers may
route ``build_shopify_discount_graphql_variables`` into a real client (not implemented here).
"""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.services.promotion_draft import PromotionDraft


class ShopifyDiscountIntegrationDisabled(RuntimeError):
    """Raised when code tries to perform a live create while the integration is off."""


def shopify_discount_integration_enabled() -> bool:
    return bool(get_settings().shopify_discount_integration_enabled)


def build_shopify_discount_graphql_variables(draft: PromotionDraft) -> dict[str, Any]:
    """
    Stable placeholder aligned with common Admin API discount patterns.

    **Not executed** against Shopify — safe to evolve. When wiring the API, map
    ``customerGets``, ``context``, and SKU selection to your discount function
    (e.g. DiscountCodeBxgy, automatic discount, or price rule legacy).

    SKU-based targeting in Shopify typically requires product/variant GIDs from
    catalog sync; until then, keep ``merchandiseIds`` empty and use titles for ops.
    """
    return {
        "draft": draft.to_dict(),
        "shopify_admin_graphql_placeholder": {
            "title": f"NosaProfit — {draft.product_name[:60]} ({draft.suggested_discount_pct:g}% / {draft.duration_days}d)",
            "summary": "Generated from NosaProfit Level-1 recommendation; confirm SKU → variant GID before publish.",
            "discount_meta": {
                "value_type": "percentage",
                "percentage": draft.suggested_discount_pct,
            },
            "window": {"duration_days": draft.duration_days},
            "targeting": {
                "skus": [draft.sku],
                "merchandise_ids_gql": [],
                "_note": "Populate variant GIDs after catalog link.",
            },
            "combines_with": {"order_discounts": False, "product_discounts": True, "shipping_discounts": True},
        },
    }


def create_shopify_discount(draft: PromotionDraft) -> str:
    """
    Future: POST/GraphQL to Shopify. Today: raises if "enabled" without client.

    Streamlit and workers should call :func:`shopify_discount_integration_enabled`
    first; when false, never call this.
    """
    if not shopify_discount_integration_enabled():
        raise ShopifyDiscountIntegrationDisabled(
            "Set NOSAPROFIT_SHOPIFY_DISCOUNT_INTEGRATION_ENABLED=true when the Admin API client is ready."
        )
    raise NotImplementedError(
        "Shopify Admin API client not wired yet. Use build_shopify_discount_graphql_variables() for implementation."
    )
