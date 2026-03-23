"""Orders explorer."""

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
from streamlit_app.ui_components import render_footer

st.set_page_config(page_title="Orders — NosaProfit", layout="wide")
st.header("Orders")

uid = st.session_state.get("active_upload_id")
dashboard = st.session_state.get("dashboard_data")
if dashboard is None or dashboard.upload_id != uid:
    if uid is None:
        st.warning("Select or process an upload from `Home`.")
        st.stop()
    with session_scope() as session:
        dashboard = get_dashboard_data(session, upload_id=uid)
    st.session_state["dashboard_data"] = dashboard

orders_df = dashboard.orders_table.copy()
if orders_df.empty:
    st.info("No orders available for this upload.")
    st.stop()

col1, col2, col3 = st.columns(3)
with col1:
    min_date = orders_df["order_date"].min()
    max_date = orders_df["order_date"].max()
    date_range = st.date_input(
        "Date range",
        value=(min_date.date(), max_date.date()) if pd.notna(min_date) and pd.notna(max_date) else (),
    )
with col2:
    countries = sorted([c for c in orders_df["country"].dropna().unique().tolist() if c])
    selected_countries = st.multiselect("Country", options=countries, default=[])
with col3:
    statuses = sorted([s for s in orders_df["status"].dropna().unique().tolist() if s])
    selected_statuses = st.multiselect("Status", options=statuses, default=[])

filtered = orders_df
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    filtered = filtered[
        (filtered["order_date"].dt.date >= start) & (filtered["order_date"].dt.date <= end)
    ]
if selected_countries:
    filtered = filtered[filtered["country"].isin(selected_countries)]
if selected_statuses:
    filtered = filtered[filtered["status"].isin(selected_statuses)]

st.dataframe(filtered, use_container_width=True, height=520)
render_footer()
