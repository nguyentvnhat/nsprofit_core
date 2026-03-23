"""Orders explorer."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from app.database import session_scope
from app.services.dashboard_service import get_overview

st.set_page_config(page_title="Orders — NosaProfit", layout="wide")
st.header("Orders")

uid = st.session_state.get("active_upload_id")
with session_scope() as session:
    dto = get_overview(session, upload_id=uid)

if dto is None:
    st.warning("Select or process an upload from **Home**.")
    st.stop()

st.dataframe(dto.orders_sample, use_container_width=True, height=480)
