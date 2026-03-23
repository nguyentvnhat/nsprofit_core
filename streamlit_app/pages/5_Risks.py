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

high_items = dashboard.signals_by_severity.get("high", []) or []
medium_items = dashboard.signals_by_severity.get("medium", []) or []
low_items = dashboard.signals_by_severity.get("low", []) or []

k1, k2, k3 = st.columns(3)
k1.metric("High severity", len(high_items))
k2.metric("Medium severity", len(medium_items))
k3.metric("Low severity", len(low_items))


def _severity_notice(severity: str, empty: bool) -> None:
    if empty:
        st.info(f"No {severity}-severity risks.")
        return

    if severity == "high":
        st.error("High-severity risks require immediate attention.")
        return
    if severity == "medium":
        st.warning("Medium-severity risks should be monitored and mitigated.")
        return
    st.success("Low-severity risks are currently manageable.")


def _render_risk_card(item: dict) -> None:
    signal_code = str(item.get("signal_code") or "UNKNOWN")
    signal_value = float(item.get("signal_value") or 0.0)
    threshold_value = float(item.get("threshold_value") or 0.0)
    entity_type = str(item.get("entity_type") or "overall")
    entity_key = item.get("entity_key")
    entity_key_text = str(entity_key) if entity_key not in (None, "") else "-"
    context = item.get("context") if isinstance(item.get("context"), dict) else {}

    with st.container(border=True):
        st.markdown(f"**{signal_code}**")
        c1, c2 = st.columns(2)
        c1.write(f"Observed value: `{signal_value:,.2f}`")
        c2.write(f"Threshold value: `{threshold_value:,.2f}`")
        st.write(f"Entity: `{entity_type}` / `{entity_key_text}`")
        if context:
            with st.expander("Context details"):
                st.json(context)


for severity in ("high", "medium", "low"):
    items = dashboard.signals_by_severity.get(severity, [])
    st.subheader(f"{severity.title()} severity ({len(items)})")
    _severity_notice(severity, empty=not bool(items))
    if not items:
        continue

    for item in items:
        _render_risk_card(item)

    with st.expander("Show raw table"):
        st.dataframe(pd.DataFrame(items), use_container_width=True, height=220)

render_footer()
