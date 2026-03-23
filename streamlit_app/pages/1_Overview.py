"""Overview page: KPI cards and high-level trend charts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from app.database import session_scope
from app.services.dashboard_service import get_dashboard_data

st.set_page_config(page_title="Overview — NosaProfit", layout="wide")
st.header("Overview")

uid = st.session_state.get("active_upload_id")
dashboard = st.session_state.get("dashboard_data")
if dashboard is None or dashboard.upload_id != uid:
    if uid is None:
        st.warning("Select or process an upload from `Home`.")
        st.stop()
    try:
        with session_scope() as session:
            dashboard = get_dashboard_data(session, upload_id=uid)
        st.session_state["dashboard_data"] = dashboard
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load dashboard data: {exc}")
        st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total revenue", f"{dashboard.kpis.get('total_revenue', 0):,.2f}")
c2.metric("Net revenue", f"{dashboard.kpis.get('net_revenue', 0):,.2f}")
c3.metric("AOV", f"{dashboard.kpis.get('aov', 0):,.2f}")
c4.metric("Total orders", f"{int(dashboard.kpis.get('total_orders', 0)):,}")

left, right = st.columns(2)
with left:
    st.subheader("Revenue over time")
    if dashboard.revenue_over_time.empty:
        st.info("No revenue timeseries available.")
    else:
        st.line_chart(dashboard.revenue_over_time)

with right:
    st.subheader("Order count over time")
    if dashboard.orders_over_time.empty:
        st.info("No order-count timeseries available.")
    else:
        st.bar_chart(dashboard.orders_over_time)

st.subheader("Recent orders")
preview = dashboard.orders_table.head(200) if isinstance(dashboard.orders_table, pd.DataFrame) else pd.DataFrame()
st.dataframe(preview, use_container_width=True, height=360)
