"""
Data Model & Ontology tab — Bordeaux Urban Digital Twin
Merges: data_models.py (cross-domain)
        + the ERD / Knowledge Graph portion of tram_b.py (Tram-specific)
"""

import streamlit as st
from app_pages import data_models, tram_b


def render():
    st.caption(
        "Cross-domain data models · plus the Tram entity model "
        "(ERD + Knowledge Graph)"
    )

    tab1, tab2 = st.tabs([
        "🔷 Data Models (Cross-Domain)",
        "🚋 Tram",
    ])

    with tab1:
        data_models.render()

    with tab2:
        tram_b.render()