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
from streamlit_app.ui_components import render_footer

st.set_page_config(page_title="Products — NosaProfit", layout="wide")
st.header("Products")

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
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Top products")
        st.dataframe(dashboard.products_table.head(100), use_container_width=True, height=420)
    with c2:
        st.metric("Top 3 SKU share", f"{dashboard.top_3_sku_share * 100:.1f}%")
        st.subheader("Revenue by SKU")
        st.bar_chart(dashboard.revenue_by_sku.head(20))

render_footer()
