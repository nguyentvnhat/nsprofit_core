"""Customer rollups (email-level MVP)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from app.database import session_scope
from app.services.dashboard_service import get_customer_breakdown

st.set_page_config(page_title="Customers — NosaProfit", layout="wide")
st.header("Customers")

uid = st.session_state.get("active_upload_id")
if uid is None:
    st.warning("Select or process an upload from **Home**.")
    st.stop()

with session_scope() as session:
    df = get_customer_breakdown(session, uid)

st.dataframe(df, use_container_width=True, height=480)
