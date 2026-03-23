"""Line-item / SKU lens."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from app.database import session_scope
from app.services.dashboard_service import get_dashboard_data
from streamlit_app.ui_components import apply_saas_theme, fmt_usd, render_footer, render_page_header

st.set_page_config(page_title="Products — NosaProfit", layout="wide")
apply_saas_theme(current_page="Products")
render_page_header("Products", "SKU performance and concentration signals.")

uid = st.session_state.get("active_upload_id")
dashboard = st.session_state.get("dashboard_data")
if dashboard is None or dashboard.upload_id != uid:
    if uid is None:
        st.warning("Select or process an upload from `Home`.")
        st.stop()
    with session_scope() as session:
        dashboard = get_dashboard_data(session, upload_id=uid)
    st.session_state["dashboard_data"] = dashboard

if dashboard.products_table.empty:
    st.info("No line items found for this upload.")
else:
    products_df = dashboard.products_table.copy()
    sku_col = products_df["sku"] if "sku" in products_df.columns else None
    if sku_col is not None:
        blank_sku_mask = sku_col.isna() | (sku_col.astype(str).str.strip() == "") | (
            sku_col.astype(str).str.upper().str.strip() == "UNKNOWN"
        )
        if bool(blank_sku_mask.any()):
            st.warning("Some product rows have missing or blank SKU values. Product-level decisions may be partially incomplete.")

    main, side = st.columns([2.2, 1])
    with main:
        st.subheader("Top products")
        st.dataframe(products_df.head(100), use_container_width=True, height=420)

    with side:
        st.metric("Top 3 SKU share", f"{dashboard.top_3_sku_share * 100:.1f}%")
        st.subheader("Revenue by SKU")
        st.bar_chart(dashboard.revenue_by_sku.head(20))

        st.subheader("Product concentration")
        share = float(dashboard.top_3_sku_share or 0.0)
        if share >= 0.7:
            st.error("Revenue concentration is very high. Performance is highly exposed to a small SKU set.")
        elif share >= 0.45:
            st.warning("Revenue concentration is moderate. Monitor mix and reduce dependency on top SKUs.")
        else:
            st.success("SKU mix appears relatively balanced across the catalog.")

        st.subheader("Top product notes")
        note_rows = products_df.head(5)
        if note_rows.empty:
            st.info("No product notes available.")
        else:
            for _, row in note_rows.iterrows():
                sku = str(row.get("sku", "") or "-")
                product_name = str(row.get("product_name", "") or "Unnamed product")
                qty = int(row.get("quantity", 0) or 0)
                rev = float(row.get("revenue", 0.0) or 0.0)
                with st.container(border=True):
                    st.markdown(f"**{product_name}**")
                    st.caption(f"SKU: {sku}")
                    st.write(f"Revenue: `{fmt_usd(rev)}` · Units: `{qty:,}`")

render_footer()
