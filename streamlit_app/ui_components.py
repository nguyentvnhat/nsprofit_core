"""Shared UI helpers for Streamlit pages."""

from __future__ import annotations

import math
import textwrap
from pathlib import Path
from typing import Any

import streamlit as st

_LOGO_CANDIDATES = (
    Path(__file__).resolve().parents[1] / "assets" / "nosaprofit.png",
    Path(
        "/Users/nhatnguyen/.cursor/projects/Users-nhatnguyen-Local-Sites-nosa-profit-core/assets/"
        "nosaprofit-42a317b8-5316-4c35-aad1-e51041cc21dd.png"
    ),
)


def brand_logo_path() -> str | None:
    for path in _LOGO_CANDIDATES:
        if path.is_file():
            return str(path)
    return None


def brand_page_icon() -> str:
    logo = brand_logo_path()
    return logo if logo else "📊"


def fmt_usd(value: float | int | None) -> str:
    try:
        v = float(value or 0.0)
    except Exception:
        v = 0.0
    if not math.isfinite(v):
        v = 0.0
    return f"${v:,.2f} USD"


# Short title + one-line explanation for non-technical readers (internal codes stay in data).
SIGNAL_CODE_FRIENDLY: dict[str, tuple[str, str]] = {
    "LOW_REPEAT_MIX": (
        "Few returning buyers",
        "Repeat customers make up a smaller share than expected, so retention may need attention.",
    ),
    "SOURCE_CONCENTRATION_RISK": (
        "Too much revenue from one traffic source",
        "Sales depend heavily on a single channel or source, which raises risk if that source weakens.",
    ),
    "HIGH_DISCOUNT_DEPENDENCY_V2": (
        "Sales lean on discounts",
        "A large part of revenue is tied to discounted orders, so performance may drop when promos pause.",
    ),
    "HIGH_DISCOUNT_DEPENDENCY": (
        "Sales lean on discounts",
        "A large part of revenue is tied to discounted orders, so performance may drop when promos pause.",
    ),
    "STACKED_DISCOUNTING": (
        "Multiple discounts stacking",
        "Compare-at, line, and order-level discounts may be combining and cutting price more than intended.",
    ),
    "VOLUME_DRIVEN_GROWTH": (
        "Growth from more orders, not bigger baskets",
        "Revenue is growing mainly through volume while average order value is not keeping pace.",
    ),
    "HERO_SKU_CONCENTRATION": (
        "A few products carry most revenue",
        "A small set of SKUs accounts for an outsized share of sales.",
    ),
    "LOW_ORDER_VALUE_PROBLEM": (
        "Many small orders",
        "A high share of orders are low-value, which can squeeze margin after acquisition cost.",
    ),
    "FREE_SHIPPING_OPPORTUNITY": (
        "Orders cluster just below free shipping",
        "Many carts sit near your free-shipping threshold—slight AOV lifts could convert more profitably.",
    ),
    "BUNDLE_OPPORTUNITY": (
        "Products often bought together",
        "Frequent pairs suggest bundle or kit offers could lift basket size.",
    ),
    "DATA_HYGIENE_ISSUE": (
        "Incomplete product data in the file",
        "Some revenue is linked to rows with missing SKU, title, or variant data, so product views can look skewed until the export is cleaned.",
    ),
    "UNSTABLE_GROWTH": (
        "Revenue jumps up and down by month",
        "Month-to-month sales swing more than a steady baseline, so forecasts and cash planning need extra care.",
    ),
    "ELEVATED_REFUND_RATE": (
        "Refunds are high versus revenue",
        "The share of revenue returned as refunds is above a typical operating range.",
    ),
    "FREE_SHIPPING_HEAVY": (
        "Free shipping used very often",
        "A high share of orders use free shipping, which can pressure margin if not priced in.",
    ),
    "TOP_CUSTOMER_CONCENTRATION_HIGH": (
        "A few customers drive a large share of sales",
        "Revenue is concentrated in a small customer set, which increases dependency risk.",
    ),
    "SKU_QUANTITY_CONCENTRATION": (
        "Unit volume focused on few SKUs",
        "Order quantity is concentrated in a narrow set of products.",
    ),
    "PRODUCT_DISCOUNT_RATE_HIGH": (
        "Heavy discounting on some products",
        "Discount rates on certain products are elevated compared with the rest of the catalog.",
    ),
    "LOW_AOV_PRESSURE": (
        "Average order size is under pressure",
        "Typical basket value sits below the reference, which can limit room for acquisition spend.",
    ),
}


def signal_friendly_pair(signal_code: str | None) -> tuple[str, str]:
    """Return (short plain-language title, one-sentence explanation)."""
    code = str(signal_code or "").strip().upper()
    if code in SIGNAL_CODE_FRIENDLY:
        return SIGNAL_CODE_FRIENDLY[code]
    if not code or code == "—":
        return "—", ""
    friendly = code.replace("_", " ").title()
    return friendly, "Triggered from your latest numbers and configured thresholds."


def signal_desc(signal_code: str | None) -> str:
    """One-line business explanation for a signal code."""
    return signal_friendly_pair(signal_code)[1]


def humanize_column_label(name: str) -> str:
    """Turn ``customer_email``-style names into ``Customer Email`` for table headers."""
    s = str(name).strip()
    if not s:
        return s
    return " ".join(part.capitalize() for part in s.split("_") if part)


def prettify_dataframe_columns(df: Any) -> Any:
    """Return a copy of a DataFrame with humanized column names (display only)."""
    import pandas as pd

    if not isinstance(df, pd.DataFrame):
        return df
    out = df.copy()
    out.columns = [humanize_column_label(c) for c in out.columns]
    return out


def prettify_records_columns(rows: list[dict[Any, Any]]) -> list[dict[Any, Any]]:
    """List-of-dicts rows with humanized keys (display only)."""
    if not rows:
        return rows
    return [{humanize_column_label(str(k)): v for k, v in row.items()} for row in rows]


def apply_saas_theme(current_page: str | None = None) -> None:
    """Apply a lightweight SaaS visual system without touching app logic."""
    st.markdown(
        '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">',
        unsafe_allow_html=True,
    )
    css = textwrap.dedent(
        """
        <style>
        :root {
          --np-bg: #f7f8fb;
          --np-surface: #ffffff;
          --np-text: #111827;
          --np-muted: #6b7280;
          --np-border: #e5e7eb;
          --np-primary: #2563eb;
        }

        html, body, [class*="css"] {
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
          color: var(--np-text);
        }

        .stApp {
          background: radial-gradient(1100px 360px at 20% -10%, #e8efff 0%, transparent 60%), var(--np-bg);
        }

        .main .block-container {
          max-width: 1400px;
          padding-top: 1.25rem;
          padding-bottom: 1.75rem;
        }

        h1, h2, h3 {
          letter-spacing: -0.01em;
        }

        [data-testid="stMetric"] {
          background: var(--np-surface);
          border: 1px solid var(--np-border);
          border-radius: 14px;
          padding: 14px 16px;
          box-shadow: 0 6px 18px rgba(17, 24, 39, 0.05);
        }

        /* Keep KPI text compact to avoid clipping in narrow columns */
        [data-testid="stMetricLabel"] {
          font-size: 0.82rem !important;
          line-height: 1.2 !important;
          white-space: normal !important;
          word-break: break-word !important;
        }

        [data-testid="stMetricValue"] {
          font-size: 1.2rem !important;
          line-height: 1.2 !important;
        }

        [data-testid="stMetricDelta"] {
          font-size: 0.78rem !important;
          white-space: normal !important;
          word-break: break-word !important;
        }

        .stButton > button {
          border-radius: 10px;
          border: 1px solid var(--np-border);
          box-shadow: 0 2px 8px rgba(17, 24, 39, 0.08);
          padding: 0.45rem 0.95rem;
          font-weight: 600;
        }

        .stButton > button[kind="primary"] {
          background: var(--np-primary);
          border-color: var(--np-primary);
          color: #fff;
        }

        [data-testid="stDataFrame"], .stPlotlyChart, .stAltairChart, .stVegaLiteChart {
          border: 1px solid var(--np-border);
          border-radius: 12px;
          overflow: hidden;
          background: var(--np-surface);
          box-shadow: 0 6px 18px rgba(17, 24, 39, 0.04);
        }

        [data-testid="stSidebar"] {
          background: #ffffff;
          border-right: 1px solid var(--np-border);
        }

        [data-testid="stSidebar"] .block-container {
          padding-top: 1rem;
        }

        /* Hide Streamlit default multipage nav to avoid duplicate menus */
        [data-testid="stSidebarNav"],
        section[data-testid="stSidebarNav"],
        div[data-testid="stSidebarNav"],
        [data-testid="stSidebarNavItems"] {
          display: none;
          visibility: hidden;
          height: 0;
          overflow: hidden;
        }

        .np-page-header {
          background: rgba(255, 255, 255, 0.9);
          border: 1px solid var(--np-border);
          border-radius: 14px;
          padding: 14px 16px;
          margin-bottom: 10px;
          box-shadow: 0 6px 18px rgba(17, 24, 39, 0.05);
        }

        /* Prevent truncation in bordered cards/containers */
        [data-testid="stVerticalBlock"] p,
        [data-testid="stVerticalBlock"] span,
        [data-testid="stVerticalBlock"] div {
          overflow-wrap: anywhere;
        }

        .np-help {
          color: #6b7280;
          margin-left: 6px;
          cursor: pointer;
          text-decoration: none;
          font-size: 0.9rem;
        }
        </style>
        """
    )
    st.markdown(css, unsafe_allow_html=True)

    _render_sidebar_menu(current_page=current_page)


def _render_sidebar_menu(current_page: str | None = None) -> None:
    labels = ["Home", "Overview", "Orders", "Products", "Customers", "Risks", "Insights", "Campaigns", "Discount"]
    page_paths = {
        "Home": "Home.py",
        "Overview": "pages/1_Overview.py",
        "Orders": "pages/2_Orders.py",
        "Products": "pages/3_Products.py",
        "Customers": "pages/4_Customers.py",
        "Risks": "pages/5_Risks.py",
        "Insights": "pages/6_Insights.py",
        "Campaigns": "pages/7_Campaigns.py",
        "Discount": "pages/8_Discount.py",
    }

    with st.sidebar:
        logo = brand_logo_path()
        if logo:
            st.image(logo, use_container_width=True)
        st.markdown("### NosaProfit")
        st.caption("Revenue Intelligence")
        try:
            from streamlit_option_menu import option_menu  # type: ignore

            selected = option_menu(
                menu_title=None,
                options=labels,
                default_index=labels.index(current_page) if current_page in labels else 0,
                icons=[
                    "house",
                    "speedometer2",
                    "receipt",
                    "box-seam",
                    "people",
                    "shield-exclamation",
                    "lightbulb",
                    "megaphone",
                    "percent",
                ],
                styles={
                    "container": {"padding": "0!important", "background-color": "transparent"},
                    "nav-link": {
                        "font-size": "14px",
                        "border-radius": "10px",
                        "padding": "8px 10px",
                        "margin": "3px 0",
                        "--hover-color": "#eef2ff",
                    },
                    "nav-link-selected": {"background-color": "#2563eb", "color": "white"},
                },
            )
            if selected and selected != current_page:
                st.switch_page(page_paths[selected])
        except Exception:
            # Safe fallback when streamlit-option-menu is unavailable.
            st.info("Install `streamlit-option-menu` for enhanced sidebar navigation.")
            for label in labels:
                if label == current_page:
                    st.markdown(f"**• {label}**")
                else:
                    st.markdown(f"- {label}")


def render_page_header(title: str, subtitle: str | None = None) -> None:
    body = f'<div class="np-page-header"><h2 style="margin:0">{title}</h2>'
    if subtitle:
        body += f'<p style="margin:.35rem 0 0 0;color:#6b7280">{subtitle}</p>'
    body += "</div>"
    st.markdown(body, unsafe_allow_html=True)


def render_footer() -> None:
    st.markdown("---")
    st.markdown(
        'Site by <a href="https://uway.asia" target="_blank" rel="noopener noreferrer">Uway Technology</a>',
        unsafe_allow_html=True,
    )
