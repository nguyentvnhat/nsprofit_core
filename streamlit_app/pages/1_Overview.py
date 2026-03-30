"""Overview page: KPI cards and high-level trend charts."""

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
from app.services.discount_recommendation import build_discount_recommendation_rows
from app.services.promotion_draft import promotion_drafts_from_discount_rows
from app.services.dashboard_service import get_dashboard_data
from streamlit_app.ui_components import (
    apply_saas_theme,
    brand_page_icon,
    fmt_usd,
    prettify_dataframe_columns,
    render_footer,
    render_page_header,
    signal_friendly_pair,
)

st.set_page_config(page_title="Overview — NosaProfit", page_icon=brand_page_icon(), layout="wide")
apply_saas_theme(current_page="Overview")
render_page_header("Overview", "Executive summary of revenue, risks, and actions.")


def _priority_badge(priority: str) -> str:
    p = (priority or "low").strip().lower()
    if p == "high":
        return "🔴 High"
    if p in {"medium", "normal"}:
        return "🟠 Medium"
    return "🟢 Low"


def _priority_key(priority: str) -> str:
    p = (priority or "").strip().lower()
    if p == "high":
        return "high"
    if p in {"normal", "medium"}:
        return "medium"
    return "low"


uid = st.session_state.get("active_upload_id")
dashboard = st.session_state.get("dashboard_data")
if (
    dashboard is None
    or dashboard.upload_id != uid
    or not hasattr(dashboard, "loss_drivers")
    or not hasattr(dashboard, "quick_wins")
):
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
c1.metric("Total revenue", fmt_usd(float(dashboard.kpis.get("total_revenue", 0) or 0.0)))
c2.metric("Net revenue", fmt_usd(float(dashboard.kpis.get("net_revenue", 0) or 0.0)))
c3.metric("AOV", fmt_usd(float(dashboard.kpis.get("aov", 0) or 0.0)))
c4.metric("Total orders", f"{int(dashboard.kpis.get('total_orders', 0)):,}")

st.subheader("Where you are losing money")
loss_drivers = getattr(dashboard, "loss_drivers", []) or []
if not loss_drivers:
    st.info("No major loss drivers detected yet for this upload.")
else:
    cols = st.columns(3)
    for idx, key in enumerate(("discount", "shipping", "refunds")):
        row = next((x for x in loss_drivers if str(x.get("driver_code")) == key), {})
        with cols[idx]:
            label = str(row.get("label") or key.title())
            amount = float(row.get("amount", 0.0) or 0.0)
            pct = float(row.get("pct_revenue", 0.0) or 0.0) * 100.0
            st.metric(label, f"{fmt_usd(amount)} ({pct:.1f}%)")
            desc = str(row.get("description") or "")
            if desc:
                st.caption(desc)

st.subheader("Quick wins this week")
try:
    with session_scope() as session:
        disc_rows = build_discount_recommendation_rows(session, int(uid))
    # Keep Overview opinionated: 3-day default and top 3 items.
    drafts = promotion_drafts_from_discount_rows(disc_rows, upload_id=int(uid), duration_days=3, limit=50)
    # Rank: high confidence first, then net revenue
    conf_rank = {"high": 3, "medium": 2, "low": 1}
    drafts_sorted = sorted(
        drafts,
        key=lambda d: (
            -conf_rank.get(str(getattr(d, "confidence", "") or "").lower().strip(), 0),
            -float(getattr(d, "net_revenue", 0.0) or 0.0),
            -float(getattr(d, "suggested_discount_pct", 0.0) or 0.0),
        ),
    )
    top_promos = drafts_sorted[:3]
except Exception:
    top_promos = []

if not top_promos:
    st.info("No product-level promotion recommendations available yet.")
else:
    for d in top_promos:
        pname = str(getattr(d, "product_name", "") or "Unnamed product")
        code = str(getattr(d, "sku", "") or "—")
        pct = float(getattr(d, "suggested_discount_pct", 0.0) or 0.0)
        days = int(getattr(d, "duration_days", 3) or 3)
        conf = str(getattr(d, "confidence", "") or "").title() or "—"
        net_rev = fmt_usd(float(getattr(d, "net_revenue", 0.0) or 0.0))
        applies = "New customers only" if str(getattr(d, "segment_policy", "") or "") == "new_customers" else "All customers"
        with st.container(border=True):
            st.markdown(f"**{pname}**")
            st.caption(
                f"Suggested discount: **{pct:.0f}%** · Duration: **{days} days** · Applies to: **{applies}**"
                f" · Confidence: **{conf}**"
            )
            st.caption(f"Recent net revenue (directional): {net_rev} · Product code: `{code}`")

    c_more, c_hint = st.columns([1, 3])
    with c_more:
        if st.button("Review all in Discount"):
            st.switch_page("pages/8_Discount.py")
    with c_hint:
        st.caption("These quick wins are pulled from the Discount page logic, so the story stays consistent across pages.")

orders_df = dashboard.orders_table.copy() if isinstance(dashboard.orders_table, pd.DataFrame) else pd.DataFrame()
filtered_orders = orders_df
if not orders_df.empty and "order_date" in orders_df.columns:
    date_series = pd.to_datetime(orders_df["order_date"], errors="coerce")
    min_date = date_series.min()
    max_date = date_series.max()
    if pd.notna(min_date) and pd.notna(max_date):
        date_range = st.date_input(
            "Date range",
            value=(min_date.date(), max_date.date()),
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start, end = date_range
            filtered_orders = orders_df.copy()
            filtered_orders["order_date"] = pd.to_datetime(filtered_orders["order_date"], errors="coerce")
            filtered_orders = filtered_orders[
                (filtered_orders["order_date"].dt.date >= start)
                & (filtered_orders["order_date"].dt.date <= end)
            ]

left, right = st.columns(2)
with left:
    st.subheader("Revenue over time")
    if filtered_orders.empty or "order_date" not in filtered_orders.columns:
        st.info("No revenue timeseries available.")
    else:
        ts = filtered_orders.dropna(subset=["order_date"]).copy()
        if ts.empty:
            st.info("No revenue timeseries available.")
        else:
            ts["day"] = pd.to_datetime(ts["order_date"], errors="coerce").dt.date
            revenue = ts.groupby("day", as_index=True)["net_revenue"].sum().to_frame("revenue")
            st.line_chart(revenue.sort_index())

with right:
    st.subheader("Order count over time")
    if filtered_orders.empty or "order_date" not in filtered_orders.columns:
        st.info("No order-count timeseries available.")
    else:
        ts = filtered_orders.dropna(subset=["order_date"]).copy()
        if ts.empty:
            st.info("No order-count timeseries available.")
        else:
            ts["day"] = pd.to_datetime(ts["order_date"], errors="coerce").dt.date
            order_count = ts.groupby("day", as_index=True)["order_name"].count().to_frame("orders")
            st.bar_chart(order_count.sort_index())

st.divider()
st.subheader("Top insights")
all_insights = list(dashboard.insights or [])
all_insights.sort(
    key=lambda x: (
        {"high": 0, "medium": 1, "low": 2}.get(_priority_key(str(x.get("priority", "low"))), 2),
        str(x.get("title") or ""),
    )
)
top_insights = all_insights[:3]
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
        money_impact = str(insight.get("money_impact") or "")
        if money_impact:
            st.caption(f"**Money impact:** {money_impact}")
        st.markdown("---")

    c_more2, c_hint2 = st.columns([1, 3])
    with c_more2:
        if st.button("See all insights"):
            st.switch_page("pages/6_Insights.py")
    with c_hint2:
        st.caption("This section uses the same insight list as the Insights page (sorted by priority first).")

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
        sig_lab, _sig_hlp = signal_friendly_pair(signal_code)
        signal_value = float(item.get("signal_value") or 0.0)
        threshold_value = float(item.get("threshold_value") or 0.0)
        entity_type = str(item.get("entity_type") or "overall")
        entity_key = item.get("entity_key")
        entity_label = str(entity_key) if entity_key not in (None, "") else "-"

        c1, c2, c3, c4, c5 = st.columns([2.2, 1.2, 1.2, 1.2, 1.2])
        c1.markdown(f"**{sig_lab}**")
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
        filtered_orders.head(200)
        if isinstance(filtered_orders, pd.DataFrame)
        else pd.DataFrame()
    )
    if preview.empty:
        st.info("No recent orders available.")
    else:
        st.dataframe(prettify_dataframe_columns(preview), use_container_width=True, height=320)

render_footer()
