"""Customer rollups (email-level MVP)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from streamlit_pkg_bootstrap import ensure_streamlit_app_package

ensure_streamlit_app_package(ROOT)

import streamlit as st

from app.database import session_scope
from app.services.dashboard_service import get_dashboard_data
from streamlit_app.ui_components import (
    apply_saas_theme,
    brand_page_icon,
    fmt_usd,
    prettify_dataframe_columns,
    render_footer,
    render_page_header,
)

st.set_page_config(page_title="Customers — NosaProfit", page_icon=brand_page_icon(), layout="wide")
apply_saas_theme(current_page="Customers")
render_page_header("Customers", "Customer mix and retention indicators.")

uid = st.session_state.get("active_upload_id")
dashboard = st.session_state.get("dashboard_data")
if dashboard is None or dashboard.upload_id != uid:
    if uid is None:
        st.warning("Select or process an upload from `Home`.")
        st.stop()
    with session_scope() as session:
        dashboard = get_dashboard_data(session, upload_id=uid)
    st.session_state["dashboard_data"] = dashboard

summary = dashboard.customer_summary
c1, c2, c3, c4 = st.columns(4)
c1.metric("New customers", f"{int(summary.get('new_customers', 0)):,}")
c2.metric("Repeat customers", f"{int(summary.get('repeat_customers', 0)):,}")
c3.metric("New customer AOV", fmt_usd(float(summary.get("new_aov", 0) or 0.0)))
c4.metric("Repeat customer AOV", fmt_usd(float(summary.get("repeat_aov", 0) or 0.0)))

st.subheader("Top customers")
st.dataframe(prettify_dataframe_columns(dashboard.top_customers), use_container_width=True, height=480)
render_footer()
