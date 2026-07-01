"""
Data & Resources tab — Bordeaux Urban Digital Twin
Merges: collectors_page.py (live collector status/fetch) + resources.py (reference links)
"""

import streamlit as st
from app_pages import collectors_page, resources


def render():
    st.caption("Live data collector status and reference links / data source documentation")

    tab1, tab2 = st.tabs([
        "⬇️ Live Collectors",
        "📋 Reference Links",
    ])

    with tab1:
        collectors_page.render()

    with tab2:
        resources.render()