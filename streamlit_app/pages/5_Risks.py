"""Risk page: signals grouped by severity."""

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

st.set_page_config(page_title="Risks — NosaProfit", layout="wide")
st.header("Risks")

uid = st.session_state.get("active_upload_id")
dashboard = st.session_state.get("dashboard_data")
if dashboard is None or dashboard.upload_id != uid:
    if uid is None:
        st.warning("Select or process an upload from `Home`.")
        st.stop()
    with session_scope() as session:
        dashboard = get_dashboard_data(session, upload_id=uid)
    st.session_state["dashboard_data"] = dashboard

for severity in ("high", "medium", "low"):
    items = dashboard.signals_by_severity.get(severity, [])
    st.subheader(f"{severity.title()} severity ({len(items)})")
    if not items:
        st.info(f"No {severity} severity signals.")
        continue
    st.dataframe(pd.DataFrame(items), use_container_width=True, height=220)

render_footer()
