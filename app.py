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
from pages import overview, catalog, data_models, ontology, resources

st.title("🏙️ Bordeaux Urban Digital Twin")
st.caption("Data infrastructure · internship project 2026")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Overview",
    "🗄️ Data catalog",
    "🔷 Data models",
    "🔗 Ontology",
    "📋 Resources",
])

with tab1: overview.render()
with tab2: catalog.render()
with tab3: data_models.render()
with tab4: ontology.render()
with tab5: resources.render()
