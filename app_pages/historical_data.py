"""
Historical Data tab — Bordeaux Urban Digital Twin
Shows historical time-series for Mobility and Energy domains,
with a time-range slider (feeds the same slider concept requested
for the Road Traffic map layer).
"""

import streamlit as st
import pandas as pd
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MOBILITY_DIR = os.path.join(DATA_DIR, "mobility")
ENERGY_DIR = os.path.join(DATA_DIR, "energy")


def _latest_csv(folder):
    if not os.path.exists(folder):
        return None
    files = [f for f in os.listdir(folder) if f.endswith(".csv")]
    if not files:
        return None
    return max([os.path.join(folder, f) for f in files], key=os.path.getmtime)


def _guess_datetime_col(df):
    for col in df.columns:
        lc = col.lower()
        if any(k in lc for k in ["date", "heure", "time", "timestamp"]):
            return col
    return None


def _guess_numeric_cols(df):
    return list(df.select_dtypes(include="number").columns)


def render_mobility():
    st.markdown("### 🚗 Mobility — Historical traffic")
    st.caption(
        "Source: `opendata.bordeaux-metropole.fr` · Bike traffic (hourly, ~2yr rolling window): "
        "`pc_velo_p` · Car traffic (annual HPM/HPS/TMJO): `comptage_trafic_YYYY`"
    )

    col_btn, col_days = st.columns([1, 2])
    with col_days:
        days = st.slider("Days of history to fetch", 7, 365, 90, key="mobility_days")
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch = st.button(
            "⬇️ Fetch bike traffic history", key="fetch_mobility", use_container_width=True
        )

    if fetch:
        with st.spinner("Fetching from Bordeaux Métropole Open Data..."):
            try:
                from collectors.mobility_collector import collect
                df = collect(days_back=days, save=True)
                if df.empty:
                    st.warning(
                        "No records returned — the API field names may not match what "
                        "the collector expects. Check the dataset page manually: "
                        "opendata.bordeaux-metropole.fr/explore/dataset/pc_velo_p/"
                    )
                else:
                    st.success(f"✅ Fetched {len(df)} records")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    latest = _latest_csv(MOBILITY_DIR)
    if not latest:
        st.info("No mobility data fetched yet. Click the button above to download bike traffic history.")
        return

    df = pd.read_csv(latest)
    st.divider()
    st.caption(f"Loaded: `{os.path.basename(latest)}` · {len(df)} rows")

    dt_col = _guess_datetime_col(df)
    if dt_col:
        try:
            df[dt_col] = pd.to_datetime(df[dt_col])
            df = df.sort_values(dt_col)
        except Exception:
            dt_col = None

    numeric_cols = _guess_numeric_cols(df)

    if not numeric_cols:
        st.dataframe(df, use_container_width=True, hide_index=True)
        return

    value_col = st.selectbox("Metric to plot", numeric_cols, key="mobility_metric")

    if dt_col:
        min_d, max_d = df[dt_col].min(), df[dt_col].max()
        if min_d < max_d:
            date_range = st.slider(
                "Time range",
                min_value=min_d.to_pydatetime(),
                max_value=max_d.to_pydatetime(),
                value=(min_d.to_pydatetime(), max_d.to_pydatetime()),
                key="mobility_time_range",
            )
            mask = (df[dt_col] >= date_range[0]) & (df[dt_col] <= date_range[1])
            plot_df = df.loc[mask, [dt_col, value_col]].set_index(dt_col)
        else:
            plot_df = df[[dt_col, value_col]].set_index(dt_col)
        st.line_chart(plot_df, color="#e8593c", height=320)
    else:
        st.bar_chart(df[[value_col]], color="#e8593c", height=320)

    with st.expander("📋 Raw data"):
        st.dataframe(df.tail(200), use_container_width=True, hide_index=True)
        st.caption(f"Showing last 200 rows of {len(df)} total")


def render_energy():
    st.markdown("### ⚡ Energy — Historical data")
    st.caption("Source: to be defined (DPE / ADEME building energy ratings, consumption per zone)")
    st.info(
        "Energy historical collector coming in next phase. "
        "Candidate datasets: DPE (ADEME, building energy class A-G), "
        "annual electricity consumption per IRIS zone."
    )


def render():
    st.caption(
        "Historical time-series for Mobility and Energy — same slider concept "
        "planned for the Road Traffic layer on the Tram B map"
    )

    tab1, tab2 = st.tabs(["🚗 Mobility", "⚡ Energy"])
    with tab1:
        render_mobility()
    with tab2:
        render_energy()