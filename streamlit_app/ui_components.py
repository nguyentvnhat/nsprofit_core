"""Shared UI helpers for Streamlit pages."""

from __future__ import annotations

import streamlit as st


def apply_saas_theme(current_page: str | None = None) -> None:
    """Apply a lightweight SaaS visual system without touching app logic."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

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
        [data-testid="stSidebarNav"] {
          display: none;
        }

        .np-page-header {
          background: rgba(255, 255, 255, 0.9);
          border: 1px solid var(--np-border);
          border-radius: 14px;
          padding: 14px 16px;
          margin-bottom: 10px;
          box-shadow: 0 6px 18px rgba(17, 24, 39, 0.05);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    _render_sidebar_menu(current_page=current_page)


def _render_sidebar_menu(current_page: str | None = None) -> None:
    labels = ["Home", "Overview", "Orders", "Products", "Customers", "Risks", "Insights"]
    page_paths = {
        "Home": "Home.py",
        "Overview": "pages/1_Overview.py",
        "Orders": "pages/2_Orders.py",
        "Products": "pages/3_Products.py",
        "Customers": "pages/4_Customers.py",
        "Risks": "pages/5_Risks.py",
        "Insights": "pages/6_Insights.py",
    }

    with st.sidebar:
        st.markdown("### NosaProfit")
        st.caption("Revenue Intelligence")
        try:
            from streamlit_option_menu import option_menu  # type: ignore

            selected = option_menu(
                menu_title=None,
                options=labels,
                default_index=labels.index(current_page) if current_page in labels else 0,
                icons=["house", "speedometer2", "receipt", "box-seam", "people", "shield-exclamation", "lightbulb"],
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
