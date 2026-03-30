"""SKU-level discount recommendations: simple promo %, product list, margin proxy bands."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from streamlit_pkg_bootstrap import ensure_streamlit_app_package

ensure_streamlit_app_package(ROOT)

import streamlit as st

from app.database import session_scope
from app.integration.shopify_discounts import (
    build_shopify_discount_graphql_variables,
    shopify_discount_integration_enabled,
)
from app.services.discount_recommendation import build_discount_recommendation_rows, get_discount_recommendation_dataframe
from app.services.promotion_draft import promotion_drafts_from_discount_rows, promotion_drafts_to_jsonable
from streamlit_app.ui_components import (
    apply_saas_theme,
    brand_page_icon,
    prettify_dataframe_columns,
    render_footer,
    render_page_header,
)

st.set_page_config(page_title="Discount — NosaProfit", page_icon=brand_page_icon(), layout="wide")
apply_saas_theme(current_page="Discount")
render_page_header(
    "Discount recommendations",
    "Per-SKU simple promo % suggestions, retained-value economics, and a proxy margin band (no COGS in export). "
    "Campaigns compares attribution buckets; this page focuses on catalog promo depth. "
    "Promotion drafts are export-ready for a future Shopify one-click create (API not wired yet).",
)

with st.expander("Discount engine roadmap (Levels 1–5)", expanded=False):
    st.markdown(
        """
| Level | Status | Focus |
|-------|--------|--------|
| **1** | **Active on this page** | Simple **%** + SKU + duration; sales & line-discount **heuristics**; human approves. |
| 2 | Planned | **Who / when / what** — segments (e.g. new vs returning), timing, slow-mover proxies. |
| 3 | Planned | **Promotion mix** — bundles, BXGY, tiered %, free-ship threshold (templates, not only flat %). |
| 4 | Planned | **Profit-aware** — contribution / margin (needs **COGS** or margin assumptions). |
| 5 | Planned | **Autonomous** — gated execution (e.g. Shopify), constraints, feedback loop. |

Details: `docs/discount-recommendation.md` in the repo.
        """
    )

st.caption("Engine: **Level 1** — basic discount recommendation (export JSON `level`: 1).")

uid = st.session_state.get("active_upload_id")
if uid is None:
    st.warning("Select or process an upload from `Home`.")
    render_footer()
    st.stop()

with session_scope() as session:
    df = get_discount_recommendation_dataframe(session, int(uid))
    raw_rows = build_discount_recommendation_rows(session, int(uid))

if df.empty:
    st.info("No line items with revenue found for this upload.")
    render_footer()
    st.stop()

st.caption(
    "Line economics: pre-discount value ≈ net line revenue + line discounts. "
    "Suggested promo % is capped near the same 15% reference used in campaign insights. "
    "Margin band is a deterministic uncertainty range around retained value, not accounting gross margin."
)

dur = st.slider("Draft promo duration (days)", min_value=1, max_value=14, value=3, step=1)
drafts = promotion_drafts_from_discount_rows(
    raw_rows,
    upload_id=int(uid),
    duration_days=int(dur),
    limit=50,
)
drafts_json = json.dumps(promotion_drafts_to_jsonable(drafts), ensure_ascii=False, indent=2)

c5, c6 = st.columns(2)
with c5:
    st.download_button(
        label="Download promotion drafts (JSON)",
        data=drafts_json.encode("utf-8"),
        file_name=f"nosa_promotion_drafts_upload_{uid}.json",
        mime="application/json",
        help="Level-1 drafts for portal or future Shopify create; schema stable via schema_version.",
    )
with c6:
    if shopify_discount_integration_enabled():
        st.info(
            "Shopify integration flag is **on** — Admin API client still **not implemented**; "
            "use JSON export or GraphQL placeholder below."
        )
    else:
        st.caption(
            "Shopify one-click create: set `NOSAPROFIT_SHOPIFY_DISCOUNT_INTEGRATION_ENABLED=true` when the client is ready."
        )

with st.expander("Shopify GraphQL placeholder (first draft only)", expanded=False):
    if drafts:
        st.code(
            json.dumps(build_shopify_discount_graphql_variables(drafts[0]), ensure_ascii=False, indent=2),
            language="json",
        )
    else:
        st.write("No drafts to preview.")

top = df.head(min(5, len(df)))
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("SKUs in view", len(df))
with c2:
    st.metric("Top SKU suggested promo", f"{float(top.iloc[0]['suggested_promo_pct']):.0f}%")
with c3:
    avg_ret = float(df["value_retained_pct"].mean())
    st.metric("Avg value retained (catalog)", f"{avg_ret:.1f}%")
with c4:
    deep = int((df["current_discount_pct"] > 25).sum())
    st.metric("SKUs already >25% off list", deep)

st.subheader("Recommended products to promote")
st.dataframe(
    prettify_dataframe_columns(
        df[
            [
                "product_name",
                "sku",
                "net_revenue",
                "current_discount_pct",
                "suggested_promo_pct",
                "margin_proxy_low_pct",
                "margin_proxy_high_pct",
                "after_promo_margin_band_low_pct",
                "after_promo_margin_band_high_pct",
            ]
        ].head(50)
    ),
    use_container_width=True,
    height=min(520, 48 + min(50, len(df)) * 36),
    hide_index=True,
)

with st.expander("Full table (all columns)", expanded=False):
    st.dataframe(
        prettify_dataframe_columns(df),
        use_container_width=True,
        height=min(560, 48 + len(df) * 35),
        hide_index=True,
    )

st.subheader("How this relates to Campaigns")
st.markdown(
    "- **Campaigns** rolls up **discount ÷ gross** per attribution bucket (UTM, source, discount code, etc.) and surfaces risks.\n"
    "- **This page** allocates **line-level discounts** to each SKU, proposes a **simple extra promo %**, and shows **retained-value / margin proxy** bands before and after that promo."
)

render_footer()
