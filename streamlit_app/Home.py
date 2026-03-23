"""Landing: upload CSV and pick active batch (UI only — logic lives in `app.services`)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from app.database import session_scope
from app.services.dashboard_service import list_uploads
from app.services.pipeline import process_shopify_csv

st.set_page_config(page_title="NosaProfit", layout="wide")
st.title("NosaProfit")
st.caption("Upload a Shopify order export to populate analytics for the dashboard pages.")

uploaded = st.file_uploader("Shopify orders export (CSV)", type=["csv"])
if uploaded is not None and st.button("Run pipeline", type="primary"):
    data = uploaded.getvalue()
    try:
        with session_scope() as session:
            uid = process_shopify_csv(session, file_bytes=data, filename=uploaded.name)
        st.session_state["active_upload_id"] = uid
        st.success(f"Processed upload id **{uid}**.")
    except Exception as exc:  # noqa: BLE001 — show user-facing error
        st.error(str(exc))

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
        format_func=lambda i: next(x for x in rows if x["id"] == i)["filename"] + f" (#{i})",
        index=default_idx,
    )
    st.session_state["active_upload_id"] = choice
else:
    st.info("No uploads yet — ingest a CSV to begin.")
