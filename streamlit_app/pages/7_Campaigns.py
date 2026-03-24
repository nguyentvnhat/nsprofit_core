"""Campaign dimension view: revenue, discount intensity, and risk by attribution bucket."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from streamlit_pkg_bootstrap import ensure_streamlit_app_package

ensure_streamlit_app_package(ROOT)

import pandas as pd
import streamlit as st

from app.database import session_scope
from app.services.dashboard_service import get_dashboard_data
from streamlit_app.ui_components import (
    apply_saas_theme,
    brand_page_icon,
    fmt_usd,
    prettify_dataframe_columns,
    render_footer,
    render_page_header,
)

st.set_page_config(page_title="Campaigns — NosaProfit", page_icon=brand_page_icon(), layout="wide")
apply_saas_theme(current_page="Campaigns")
render_page_header(
    "Campaigns",
    "Compare attribution buckets (UTM, landing, source, discount code) using the same metrics, signals, and rules as store-level analysis.",
)

uid = st.session_state.get("active_upload_id")
dashboard = st.session_state.get("dashboard_data")
if dashboard is None or dashboard.upload_id != uid:
    if uid is None:
        st.warning("Select or process an upload from `Home`.")
        st.stop()
    with session_scope() as session:
        dashboard = get_dashboard_data(session, upload_id=uid)
    st.session_state["dashboard_data"] = dashboard
elif not hasattr(dashboard, "campaign_summary_table"):
    with session_scope() as session:
        dashboard = get_dashboard_data(session, upload_id=uid)
    st.session_state["dashboard_data"] = dashboard

summary_rows = list(getattr(dashboard, "campaign_summary_table", None) or [])
risks_rows = list(getattr(dashboard, "top_campaign_risks", None) or [])
insights_rows = list(getattr(dashboard, "top_campaign_insights", None) or [])
campaign_results = list(getattr(dashboard, "campaign_results", None) or [])

if not summary_rows:
    st.info(
        "No campaign buckets found for this upload. "
        "Re-process the CSV after upgrading, or ensure exports include Source / UTM / Landing / Referring / Discount Code "
        "so orders can be grouped beyond **unknown**."
    )
    render_footer()
    st.stop()

st.caption("Discount rate = discounts ÷ gross revenue (0–1) within each bucket. Currency amounts are USD.")

df = pd.DataFrame(summary_rows)
if not df.empty and "discount_rate" in df.columns:
    df = df.copy()
    df["discount_pct"] = (df["discount_rate"].astype(float) * 100.0).round(2)
    df = df.drop(columns=["discount_rate"], errors="ignore")

display_df = prettify_dataframe_columns(df)
st.subheader("Summary by campaign")
st.dataframe(
    display_df,
    use_container_width=True,
    height=min(420, 48 + len(summary_rows) * 36),
    hide_index=True,
)

c1, c2, c3 = st.columns(3)
c1.metric("Campaign buckets", len(summary_rows))
if not df.empty and "orders" in df.columns:
    c2.metric("Orders in view", int(df["orders"].sum()))
if not df.empty and "net_revenue" in summary_rows[0]:
    total_net = sum(float(r.get("net_revenue") or 0) for r in summary_rows)
    c3.metric("Net revenue (summed)", fmt_usd(total_net))

st.divider()
st.subheader("High-severity signals by campaign")
if not risks_rows:
    st.info("No high-severity campaign-level signals in the current top slice.")
else:
    rdf = pd.DataFrame(risks_rows)
    cols = [c for c in ("campaign", "signal_code", "severity", "entity_type", "signal_value", "threshold_value") if c in rdf.columns]
    if cols:
        st.dataframe(prettify_dataframe_columns(rdf[cols]), use_container_width=True, hide_index=True, height=280)

st.subheader("Top campaign insights")
if not insights_rows:
    st.info("No high/medium campaign-level insights in the current top slice.")
else:
    for row in insights_rows[:15]:
        camp = str(row.get("campaign") or "unknown")
        title = str(row.get("title") or "Insight")
        with st.expander(f"**{camp}** — {title}"):
            st.write(str(row.get("summary") or ""))
            st.caption(f"Priority: {str(row.get('priority') or '').title()} · {str(row.get('category') or '')}")

with st.expander("Per-campaign detail (pick a bucket)"):
    if not campaign_results:
        st.write("No detailed payloads.")
    else:
        labels = [str(r.get("campaign") or "unknown") for r in campaign_results]
        choice = st.selectbox("Campaign", options=labels, index=0)
        picked = next((r for r in campaign_results if str(r.get("campaign")) == choice), None)
        if picked and isinstance(picked, dict):
            summ = picked.get("summary") or {}
            st.markdown(
                f"**Orders:** {picked.get('order_count', 0)} · "
                f"**Net revenue:** {fmt_usd(float(summ.get('net_revenue') or 0))} · "
                f"**Risk:** {str(summ.get('risk_level') or 'low').title()}"
            )
            sig_n = len(picked.get("signals") or [])
            ins_n = len(picked.get("insights") or [])
            st.caption(f"{sig_n} signals · {ins_n} insights in this bucket.")
            st.json(
                {
                    "summary": summ,
                    "signal_codes": sorted(
                        {str(s.get("signal_code")) for s in (picked.get("signals") or []) if isinstance(s, dict)}
                    ),
                    "insight_titles": [
                        str(i.get("title"))
                        for i in (picked.get("insights") or [])[:20]
                        if isinstance(i, dict)
                    ],
                }
            )

render_footer()
