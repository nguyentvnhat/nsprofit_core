"""Shared UI helpers for Streamlit pages."""

from __future__ import annotations

import streamlit as st


def render_footer() -> None:
    st.markdown("---")
    st.markdown(
        'Site by <a href="https://uway.asia" target="_blank" rel="noopener noreferrer">Uway Technology</a>',
        unsafe_allow_html=True,
    )
