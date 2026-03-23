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
from streamlit_app.ui_components import apply_saas_theme, render_footer, render_page_header

st.set_page_config(page_title="Overview — NosaProfit", layout="wide")
apply_saas_theme(current_page="Overview")
render_page_header("Overview", "Executive summary of revenue, risks, and actions.")


def _priority_badge(priority: str) -> str:
    p = (priority or "low").strip().lower()
    if p == "high":
        return "🔴 High"
    if p in {"medium", "normal"}:
        return "🟠 Medium"
    return "🟢 Low"

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

st.divider()
st.subheader("Top insights")
top_insights = (dashboard.insights or [])[:3]
if not top_insights:
    st.info("No insights available yet for this upload.")
else:
    for insight in top_insights:
        title = str(insight.get("title") or "Untitled insight")
        priority = _priority_badge(str(insight.get("priority") or "low"))
        summary = str(insight.get("summary") or "")
        implication = str(insight.get("implication") or "")
        action = str(insight.get("action") or "")
        st.markdown(f"#### {title}  \n{priority}")
        if summary:
            st.write(summary)
        if implication:
            st.caption(f"**Implication:** {implication}")
        if action:
            st.caption(f"**Action:** {action}")
        st.markdown("---")

st.subheader("Top risks")
signals_by_sev = dashboard.signals_by_severity or {}
high_risks = signals_by_sev.get("high", []) or []
medium_risks = signals_by_sev.get("medium", []) or []
low_risks = signals_by_sev.get("low", []) or []

r1, r2, r3 = st.columns(3)
r1.metric("High risks", len(high_risks))
r2.metric("Medium risks", len(medium_risks))
r3.metric("Low risks", len(low_risks))

if not high_risks:
    st.info("No high-severity risks detected.")
else:
    st.caption("High-priority risk signals")
    for item in high_risks[:2]:
        signal_code = str(item.get("signal_code") or "UNKNOWN")
        signal_value = float(item.get("signal_value") or 0.0)
        threshold_value = float(item.get("threshold_value") or 0.0)
        entity_type = str(item.get("entity_type") or "overall")
        entity_key = item.get("entity_key")
        entity_label = str(entity_key) if entity_key not in (None, "") else "-"

        c1, c2, c3, c4, c5 = st.columns([2.2, 1.2, 1.2, 1.2, 1.2])
        c1.markdown(f"**{signal_code}**")
        c2.markdown(f"Value: `{signal_value:,.2f}`")
        c3.markdown(f"Threshold: `{threshold_value:,.2f}`")
        c4.markdown(f"Type: `{entity_type}`")
        c5.markdown(f"Key: `{entity_label}`")

st.subheader("Recommended actions")
actions: list[str] = []
for insight in dashboard.insights or []:
    act = str(insight.get("action") or "").strip()
    if act:
        actions.append(act)
    if len(actions) >= 3:
        break

if not actions:
    st.info("No recommended actions available yet.")
else:
    for idx, action in enumerate(actions, start=1):
        st.markdown(f"{idx}. {action}")

with st.expander("Recent orders preview"):
    preview = (
        dashboard.orders_table.head(200)
        if isinstance(dashboard.orders_table, pd.DataFrame)
        else pd.DataFrame()
    )
    if preview.empty:
        st.info("No recent orders available.")
    else:
        st.dataframe(preview, use_container_width=True, height=320)

render_footer()
