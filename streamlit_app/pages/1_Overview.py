"""Overview KPIs and sample order table."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from app.database import session_scope
from app.services.dashboard_service import get_overview

st.set_page_config(page_title="Overview — NosaProfit", layout="wide")
st.header("Overview")

uid = st.session_state.get("active_upload_id")
with session_scope() as session:
    dto = get_overview(session, upload_id=uid)

if dto is None:
    st.warning("Select or process an upload from **Home**.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Net revenue", f"{dto.kpis.get('net_revenue_total', 0):,.2f}")
c2.metric("Orders", f"{int(dto.kpis.get('order_count', 0))}")
c3.metric("AOV (net)", f"{dto.kpis.get('average_order_value_net', 0):,.2f}")
c4.metric("Discount / gross", f"{dto.kpis.get('discount_to_gross_ratio', 0) * 100:.1f}%")

st.subheader("Revenue mix (snapshot)")
mix = pd.DataFrame(
    {
        "bucket": ["Net revenue", "Gross revenue", "Discounts", "Refunds"],
        "amount": [
            dto.kpis.get("net_revenue_total", 0),
            dto.kpis.get("gross_revenue_total", 0),
            dto.kpis.get("discount_total", 0),
            dto.kpis.get("refund_total", 0),
        ],
    }
).set_index("bucket")
st.bar_chart(mix)

st.subheader("Recent orders (sample)")
st.dataframe(dto.orders_sample, use_container_width=True)

st.subheader("Signals")
st.dataframe(dto.signals, use_container_width=True)
