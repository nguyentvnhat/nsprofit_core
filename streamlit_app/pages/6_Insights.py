"""Rule-generated narratives."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from app.database import session_scope
from app.services.dashboard_service import get_overview

st.set_page_config(page_title="Insights — NosaProfit", layout="wide")
st.header("Insights")

uid = st.session_state.get("active_upload_id")
with session_scope() as session:
    dto = get_overview(session, upload_id=uid)

if dto is None:
    st.warning("Select or process an upload from **Home**.")
    st.stop()

for ins in dto.insights:
    with st.expander(f"{ins['title']} ({ins['priority']})", expanded=True):
        st.write(ins["summary"])
        if ins.get("implication_text"):
            st.markdown(f"**Implication:** {ins['implication_text']}")
        if ins.get("recommended_action"):
            st.markdown(f"**Action:** {ins['recommended_action']}")
