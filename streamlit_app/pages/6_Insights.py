"""Rule-generated narratives."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from app.database import session_scope
from app.services.dashboard_service import get_dashboard_data

st.set_page_config(page_title="Insights — NosaProfit", layout="wide")
st.header("Insights")

uid = st.session_state.get("active_upload_id")
dashboard = st.session_state.get("dashboard_data")
if dashboard is None or dashboard.upload_id != uid:
    if uid is None:
        st.warning("Select or process an upload from `Home`.")
        st.stop()
    with session_scope() as session:
        dashboard = get_dashboard_data(session, upload_id=uid)
    st.session_state["dashboard_data"] = dashboard

if not dashboard.insights:
    st.info("No insights generated for this upload.")
    st.stop()

def _priority_badge(priority: str) -> str:
    p = (priority or "").strip().lower()
    if p == "high":
        return "🔴 High"
    if p == "normal":
        return "🟡 Medium"
    return "🟢 Low"


for insight in dashboard.insights:
    badge = _priority_badge(insight.get("priority", "low"))
    with st.container(border=True):
        st.markdown(f"### {insight.get('title', 'Insight')}")
        st.caption(f"{badge} | Category: {insight.get('category', 'general')}")
        st.write(insight.get("summary", ""))
        with st.expander("Details"):
            st.markdown(f"**Implication:** {insight.get('implication') or 'N/A'}")
            st.markdown(f"**Action:** {insight.get('action') or 'N/A'}")
