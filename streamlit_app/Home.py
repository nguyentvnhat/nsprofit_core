"""Home page: upload Shopify CSV and run dashboard pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from app.database import session_scope
from app.services.dashboard_service import list_uploads, run_dashboard_pipeline
from streamlit_app.ui_components import apply_saas_theme, render_footer, render_page_header

st.set_page_config(page_title="NosaProfit", layout="wide")
apply_saas_theme(current_page="Home")
render_page_header("NosaProfit", "Upload a Shopify CSV, process it, then explore KPIs, risks, and insights.")

uploaded = st.file_uploader("Shopify orders export (CSV)", type=["csv"])
if st.button("Run pipeline", type="primary"):
    if uploaded is None:
        st.info("Upload a CSV file to run the pipeline.")
    else:
        data = uploaded.getvalue()
        try:
            with session_scope() as session:
                dashboard = run_dashboard_pipeline(
                    session,
                    file_bytes=data,
                    filename=uploaded.name,
                )
            st.session_state["active_upload_id"] = dashboard.upload_id
            st.session_state["dashboard_data"] = dashboard
            st.success(f"Processed upload **#{dashboard.upload_id}** successfully.")
        except Exception as exc:  # noqa: BLE001 - user-friendly pipeline boundary
            st.error(f"Pipeline failed: {exc}")

with session_scope() as session:
    rows = list_uploads(session)

if rows:
    ids = [r["id"] for r in rows]
    default_idx = 0
    if "active_upload_id" in st.session_state and st.session_state["active_upload_id"] in ids:
        default_idx = ids.index(st.session_state["active_upload_id"])
    choice = st.selectbox(
        "Active upload for this session",
        options=ids,
        format_func=lambda i: next(x for x in rows if x["id"] == i)["file_name"] + f" (#{i})",
        index=default_idx,
    )
    st.session_state["active_upload_id"] = choice
    st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    st.info("No uploads yet — ingest a CSV to begin.")

render_footer()
