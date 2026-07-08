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
st.markdown("""
<style>
h1 { font-size: 36px !important; font-weight: 800 !important; }
h2 { font-size: 27px !important; font-weight: 750 !important; }
h3 { font-size: 21px !important; font-weight: 700 !important; }

/* هم روی خودِ تب، هم روی متن داخلش (p) اعمال می‌شه */
.stTabs [data-baseweb="tab"],
.stTabs [data-baseweb="tab"] p,
.stTabs button[role="tab"],
.stTabs button[role="tab"] p {
    font-size: 17px !important;
    font-weight: 700 !important;
}

/* Streamlit's default caption is opacity:0.6 + 14px, which reads as faded —
   raise both legibility knobs directly rather than just bumping font-size. */
[data-testid="stCaptionContainer"] {
    font-size: 15px !important;
    opacity: 0.85 !important;
}
[data-testid="stCaptionContainer"] p {
    color: rgb(35, 35, 40) !important;
}

[data-testid="stMetricLabel"] p {
    font-size: 16px !important;
    font-weight: 650 !important;
}
</style>
""", unsafe_allow_html=True)

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app_pages import (
    overview, catalog,
    data_model_ontology, city_dashboard, data_resources,
)

st.title("🏙️ Bordeaux Urban Digital Twin")
st.caption("Data infrastructure · internship project 2026")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Overview",
    "🗄️ Data catalog",
    "🔷 Data Model & Ontology",
    "🏙️ City Dashboard",
    "📥 Data & Resources",
])

with tab1: overview.render()
with tab2: catalog.render()
with tab3: data_model_ontology.render()
with tab4: city_dashboard.render()
with tab5: data_resources.render()