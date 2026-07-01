"""
City Dashboard tab — Bordeaux Urban Digital Twin
The visual/interactive front-end of the project: live Tram map +
historical Mobility trends (bicycle, road traffic). More modes
and lines will be added here over time (see mobility_config.py).
"""

import streamlit as st
from app_pages import simulation, historical_data


def render():
    st.caption(
        "Live network view and historical trends — the interactive part of the dashboard"
    )

    tab1, tab2 = st.tabs([
        "🚋 Tram — Live Map",
        "🚦 Mobility — Historical",
    ])

    with tab1:
        simulation.render()

    with tab2:
        historical_data.render()