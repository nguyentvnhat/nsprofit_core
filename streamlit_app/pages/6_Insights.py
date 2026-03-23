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
from streamlit_app.ui_components import apply_saas_theme, render_footer, render_page_header

st.set_page_config(page_title="Insights — NosaProfit", layout="wide")
apply_saas_theme(current_page="Insights")
render_page_header("Insights", "Prioritized insights and recommended actions.")

uid = st.session_state.get("active_upload_id")
dashboard = st.session_state.get("dashboard_data")
if dashboard is None or dashboard.upload_id != uid or not hasattr(dashboard, "money_summary"):
    if uid is None:
        st.warning("Select or process an upload from `Home`.")
        st.stop()
    with session_scope() as session:
        dashboard = get_dashboard_data(session, upload_id=uid)
    st.session_state["dashboard_data"] = dashboard

if not dashboard.insights:
    st.info("No insights generated for this upload.")
    st.stop()


def _priority_key(priority: str) -> str:
    p = (priority or "").strip().lower()
    if p == "high":
        return "high"
    if p in {"normal", "medium"}:
        return "medium"
    return "low"


def _priority_badge(priority_key: str) -> str:
    if priority_key == "high":
        return "🔴 High"
    if priority_key == "medium":
        return "🟡 Medium"
    return "🟢 Low"


grouped: dict[str, list[dict]] = {"high": [], "medium": [], "low": []}
for insight in dashboard.insights:
    grouped[_priority_key(str(insight.get("priority", "low")))].append(insight)

all_categories = sorted(
    {
        str(i.get("category") or "general").strip()
        for i in dashboard.insights
        if str(i.get("category") or "").strip()
    }
)
category_options = ["All categories", *all_categories]
selected_category = st.selectbox("Filter by category", options=category_options, index=0)

total_insights = len(dashboard.insights)
high_count = len(grouped["high"])
medium_count = len(grouped["medium"])
low_count = len(grouped["low"])

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total insights", total_insights)
k2.metric("High priority", high_count)
k3.metric("Medium priority", medium_count)
k4.metric("Low priority", low_count)


def _render_insight_card(insight: dict, priority_key: str) -> None:
    badge = _priority_badge(priority_key)
    category = str(insight.get("category", "general"))
    category_label = category.replace("_", " ").title()
    insight_key = str(insight.get("insight_code") or insight.get("title") or "insight")
    feedback_key = f"insight_feedback::{insight_key}"
    feedback = st.session_state.get(feedback_key, "")

    with st.container(border=True):
        st.markdown(f"### {insight.get('title', 'Insight')}")
        st.caption(f"{badge}")
        st.markdown(f"`{category_label}`")
        st.write(insight.get("summary", ""))
        st.markdown(f"**Implication:** {insight.get('implication') or 'N/A'}")
        st.markdown(f"**Action:** {insight.get('action') or 'N/A'}")
        money_impact = str(insight.get("money_impact") or "").strip()
        trade_off = str(insight.get("trade_off") or "").strip()
        confidence = str(insight.get("confidence") or "").strip()
        if money_impact:
            st.markdown(f"**Money impact:** {money_impact}")
        if trade_off:
            st.markdown(f"**Trade-off:** {trade_off}")
        if confidence:
            st.caption(f"Confidence: {confidence.title()}")
        b1, b2, b3 = st.columns([1, 1, 5])
        if b1.button("👍 Like", key=f"{insight_key}::like"):
            st.session_state[feedback_key] = "liked"
        if b2.button("👎 Dislike", key=f"{insight_key}::dislike"):
            st.session_state[feedback_key] = "disliked"
        if feedback == "liked":
            b3.caption("Feedback: Liked")
        elif feedback == "disliked":
            b3.caption("Feedback: Disliked")


for section_key, section_title in (
    ("high", "High Priority"),
    ("medium", "Medium Priority"),
    ("low", "Low Priority"),
):
    st.subheader(section_title)
    items = grouped[section_key]
    if selected_category != "All categories":
        items = [x for x in items if str(x.get("category", "")).strip() == selected_category]
    if not items:
        st.info(f"No {section_title.lower()} insights.")
        continue
    for insight in items:
        _render_insight_card(insight, section_key)

render_footer()
