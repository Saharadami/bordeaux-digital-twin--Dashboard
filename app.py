"""
Bordeaux Urban Digital Twin — Data Dashboard
Run: python -m streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Bordeaux Digital Twin",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from pages import overview, catalog, data_models, ontology, resources, collectors_page, tram_b, simulation

st.title("🏙️ Bordeaux Urban Digital Twin")
st.caption("Data infrastructure · internship project 2026")

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📊 Overview",
    "🗄️ Data catalog",
    "🔷 Data models",
    "🔗 Ontology",
    "🚋 Tram B",
    "🗺️ Simulation",
    "⬇️ Collectors",
    "📋 Resources",
])

with tab1: overview.render()
with tab2: catalog.render()
with tab3: data_models.render()
with tab4: ontology.render()
with tab5: tram_b.render()
with tab6: simulation.render()
with tab7: collectors_page.render()
with tab8: resources.render()