"""Risk page: signals grouped by severity."""

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

st.set_page_config(page_title="Risks — NosaProfit", page_icon=brand_page_icon(), layout="wide")
apply_saas_theme(current_page="Risks")
render_page_header("Risks", "Severity-based risk monitoring for fast decision-making.")

uid = st.session_state.get("active_upload_id")
dashboard = st.session_state.get("dashboard_data")
if dashboard is None or dashboard.upload_id != uid or not hasattr(dashboard, "money_summary"):
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
    money = getattr(dashboard, "money_summary", {}) or {}
    signal_label, signal_help = _signal_label_and_help(signal_code)

    with st.container(border=True):
        st.markdown(
            f"<b>{signal_label}</b> "
            f"<span class=\"np-help\" title=\"{signal_help}\"><i class=\"fa-solid fa-circle-info\"></i></span>",
            unsafe_allow_html=True,
        )
        st.caption(f"Code: {signal_code}")
        c1, c2 = st.columns(2)
        c1.markdown(
            "<span title=\"Observed metric value for this risk condition. "
            "When observed value exceeds (or breaches) threshold, risk is considered active.\">"
            "Observed value <span class=\"np-help\"><i class=\"fa-solid fa-circle-info\"></i></span></span>",
            unsafe_allow_html=True,
        )
        c1.write(f"`{signal_value:,.2f}`")
        c2.markdown(
            "<span title=\"Configured comparison reference used to trigger this risk.\">"
            "Threshold value <span class=\"np-help\"><i class=\"fa-solid fa-circle-info\"></i></span></span>",
            unsafe_allow_html=True,
        )
        c2.write(f"`{threshold_value:,.2f}`")
        if entity_key_text == "-":
            st.write(f"Entity: `{entity_type}`")
        else:
            st.write(f"Entity: `{entity_type}` / `{entity_key_text}`")
        hint = _impact_hint(item, money)
        if hint:
            st.caption(f"**Estimated business impact:** {hint}")
        if context:
            with st.expander("Business context"):
                labels: dict[str, str] = {
                    "active": "Triggered",
                    "top_source_share": "Top source share",
                    "discount_rate": "Discount rate",
                    "low_value_order_ratio": "Low-value order ratio",
                    "orders_near_free_shipping_threshold": "Near free-shipping threshold ratio",
                    "revenue_growth": "Revenue growth",
                    "aov_growth": "AOV growth",
                    "max_abs_mom_revenue_growth": "Max month-over-month revenue swing",
                    "blank_sku_revenue": "Revenue with missing SKU",
                    "compare_at_discount_total": "Compare-at discount total",
                    "discount_amount_total": "Discount amount total",
                    "max_pair_count": "Top bundle pair count",
                    "bundle_pairs_count": "Bundle pair combinations",
                    "months_observed": "Months observed",
                    "refund_rate_pct": "Refund rate (%)",
                    "free_shipping_rate_pct": "Free shipping rate (%)",
                    "repeat_customer_rate_pct": "Repeat customer rate (%)",
                    "top_customer_revenue_share_pct": "Top customer revenue share (%)",
                }
                for key, value in context.items():
                    label = labels.get(str(key), str(key).replace("_", " ").title())
                    if isinstance(value, bool):
                        text_value = "Yes" if value else "No"
                    elif isinstance(value, (int, float)):
                        text_value = f"{value:,.2f}"
                    else:
                        text_value = str(value)
                    st.write(f"**{label}:** {text_value}")


def _impact_hint(item: dict, money_summary: dict) -> str:
    signal_code = str(item.get("signal_code") or "")
    code = (signal_code or "").strip().upper()
    context = item.get("context") if isinstance(item.get("context"), dict) else {}
    signal_value = float(item.get("signal_value") or 0.0)

    # Prefer signal-local context/value over global fallback when available.
    if "discount_rate_pct" in context:
        discount_pct = float(context.get("discount_rate_pct") or 0.0)
    elif "discount_rate" in context:
        raw = float(context.get("discount_rate") or 0.0)
        discount_pct = raw * 100.0 if raw <= 1.0 else raw
    elif "DISCOUNT" in code:
        discount_pct = signal_value * 100.0 if signal_value <= 1.0 else signal_value
    else:
        discount_pct = float(money_summary.get("discount_as_pct_revenue", 0.0) or 0.0) * 100.0

    shipping_pct = float(money_summary.get("shipping_as_pct_revenue", 0.0) or 0.0) * 100.0
    refund_pct = float(money_summary.get("refund_as_pct_revenue", 0.0) or 0.0) * 100.0
    discount_amt = float(money_summary.get("discount_amount_total", 0.0) or 0.0)
    shipping_amt = float(money_summary.get("shipping_amount_total", 0.0) or 0.0)
    refund_amt = float(money_summary.get("refunded_amount_total", 0.0) or 0.0)
    if "DISCOUNT" in code:
        return (
            f"This may indicate margin leakage through discounting "
            f"({fmt_usd(discount_amt)}, ~{discount_pct:.1f}% of gross revenue)."
        )
    if "SHIPPING" in code:
        return (
            f"This may limit profitable scaling as shipping absorbs "
            f"{fmt_usd(shipping_amt)} (~{shipping_pct:.1f}% of revenue)."
        )
    if "REFUND" in code:
        return (
            f"This may reflect post-purchase leakage, with refunds at "
            f"{fmt_usd(refund_amt)} (~{refund_pct:.1f}% of revenue)."
        )
    if "CONCENTRATION" in code:
        return "This suggests over-reliance on a narrow product or channel mix."
    if "LOW_ORDER_VALUE" in code or "AOV" in code or "BUNDLE" in code:
        return "This may limit profitable scaling if acquisition costs rise."
    return ""


def _signal_label_and_help(signal_code: str) -> tuple[str, str]:
    code = (signal_code or "").strip().upper()
    mapping: dict[str, tuple[str, str]] = {
        "LOW_REPEAT_MIX": (
            "Low Repeat Customer Mix",
            "Share of repeat customers is below target, suggesting weaker retention quality.",
        ),
        "SOURCE_CONCENTRATION_RISK": (
            "Source Concentration Risk",
            "Revenue dependency on one source/channel is high.",
        ),
        "HIGH_DISCOUNT_DEPENDENCY_V2": (
            "High Discount Dependency",
            "Sales performance appears heavily tied to discounting.",
        ),
        "STACKED_DISCOUNTING": (
            "Stacked Discounting",
            "Multiple discount mechanisms may be active at the same time.",
        ),
        "VOLUME_DRIVEN_GROWTH": (
            "Volume-Driven Growth",
            "Revenue growth is likely coming from volume, not basket value expansion.",
        ),
        "HERO_SKU_CONCENTRATION": (
            "Hero SKU Concentration",
            "A large share of revenue is concentrated in very few SKUs.",
        ),
        "LOW_ORDER_VALUE_PROBLEM": (
            "Low Order Value Problem",
            "A high portion of orders are low-value, constraining margin headroom.",
        ),
        "FREE_SHIPPING_OPPORTUNITY": (
            "Free Shipping Opportunity",
            "Many baskets sit just below free-shipping threshold, indicating AOV lift potential.",
        ),
        "BUNDLE_OPPORTUNITY": (
            "Bundle Opportunity",
            "Frequent product pairs suggest bundle design opportunity.",
        ),
        "DATA_HYGIENE_ISSUE": (
            "Data Hygiene Issue",
            "Missing/blank SKU-linked revenue reduces decision reliability.",
        ),
        "UNSTABLE_GROWTH": (
            "Unstable Growth",
            "Month-to-month revenue swings are elevated.",
        ),
        "ELEVATED_REFUND_RATE": (
            "Elevated Refund Rate",
            "Refund proportion is above expected operating range.",
        ),
        "FREE_SHIPPING_HEAVY": (
            "Heavy Free Shipping Usage",
            "Free shipping rate is high and may pressure retained revenue.",
        ),
    }
    if code in mapping:
        return mapping[code]
    return code.replace("_", " ").title(), "Signal triggered from current metrics and configured thresholds."


for severity in ("high", "medium", "low"):
    items = dashboard.signals_by_severity.get(severity, [])
    st.subheader(f"{severity.title()} severity ({len(items)})")
    _severity_notice(severity, empty=not bool(items))
    if not items:
        continue

    for item in items:
        _render_risk_card(item)

    with st.expander("Show raw table"):
        st.dataframe(prettify_dataframe_columns(pd.DataFrame(items)), use_container_width=True, height=220)

render_footer()
