"""
Data Model & Ontology tab — Bordeaux Urban Digital Twin
Merges: data_models.py (cross-domain) + ontology.py (cross-domain)
        + the ERD / Knowledge Graph portion of tram_b.py (Tram-specific)
"""

import streamlit as st
from app_pages import data_models, ontology, tram_b


def render():
    st.caption(
        "Cross-domain data models and ontology · plus the Tram entity model "
        "(ERD + Knowledge Graph)"
    )

    tab1, tab2, tab3 = st.tabs([
        "🔷 Data Models (Cross-Domain)",
        "🔗 Ontology (Cross-Domain)",
        "🚋 Tram",
    ])

    with tab1:
        data_models.render()

    with tab2:
        ontology.render()

    with tab3:
        tram_b.render()