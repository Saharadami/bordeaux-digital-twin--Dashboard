"""
Data Collectors tab — Bordeaux Urban Digital Twin
Shows status of all collectors and fetched data visualizations
"""

import streamlit as st
import pandas as pd
import os
import sys

# Add project root to path so we can import collectors
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DOMAIN_META = {
    "Weather":    {"icon": "🌤️", "color": "#3b8bd4"},
    "AirQuality": {"icon": "🌬️", "color": "#1d9e75"},
    "Mobility":   {"icon": "🚗", "color": "#e8593c"},
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def get_collector_status(domain: str) -> dict:
    """Check if data exists for a domain and return status info."""
    domain_dir = os.path.join(DATA_DIR, domain.lower().replace(" ", "_"))

    if not os.path.exists(domain_dir):
        return {"status": "no_data", "files": 0, "latest": None, "rows": 0}

    files = [f for f in os.listdir(domain_dir) if f.endswith(".csv")]
    if not files:
        return {"status": "no_data", "files": 0, "latest": None, "rows": 0}

    latest_path = max(
        [os.path.join(domain_dir, f) for f in files],
        key=os.path.getmtime
    )
    latest_time = os.path.getmtime(latest_path)
    from datetime import datetime
    latest_str = datetime.fromtimestamp(latest_time).strftime("%Y-%m-%d %H:%M")

    try:
        df = pd.read_csv(latest_path)
        rows = len(df)
    except Exception:
        rows = 0

    return {
        "status": "ok",
        "files": len(files),
        "latest": latest_str,
        "latest_path": latest_path,
        "rows": rows,
    }


def render_weather():
    st.markdown("### 🌤️ Weather — Open-Meteo")
    st.caption("Source: `api.open-meteo.com` · No API key required · Hourly data · Météo-France model")

    status = get_collector_status("weather")

    col1, col2, col3 = st.columns(3)
    col1.metric("Status", "✅ Data available" if status["status"] == "ok" else "❌ No data yet")
    col2.metric("Records", status["rows"] if status["rows"] else "—")
    col3.metric("Last fetch", status["latest"] if status["latest"] else "—")

    col_btn, col_days = st.columns([1, 2])
    with col_days:
        days = st.slider("Days of history", 7, 90, 30, key="weather_days")
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch = st.button("⬇️ Fetch weather data", key="fetch_weather", use_container_width=True)

    if fetch:
        with st.spinner("Fetching from Open-Meteo..."):
            try:
                from collectors.weather_collector import collect
                df = collect(days_back=days, save=True)
                st.success(f"✅ Fetched {len(df)} records ({days} days)")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    # Show data if available
    if status["status"] == "ok":
        df = pd.read_csv(status["latest_path"], parse_dates=["timestamp"])
        st.divider()

        # Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Avg Temperature", f"{df['temperature_c'].mean():.1f}°C")
        m2.metric("Total Precipitation", f"{df['precipitation_mm'].sum():.1f}mm")
        m3.metric("Avg Wind Speed", f"{df['wind_speed_kmh'].mean():.1f}km/h")
        m4.metric("Avg Solar Radiation", f"{df['solar_rad_wm2'].mean():.0f}W/m²")

        # Charts
        tab_temp, tab_rain, tab_wind, tab_raw = st.tabs([
            "🌡️ Temperature", "🌧️ Precipitation", "💨 Wind", "📋 Raw data"
        ])

        with tab_temp:
            st.line_chart(
                df.set_index("timestamp")[["temperature_c"]],
                color="#e8593c",
                height=300,
            )

        with tab_rain:
            st.bar_chart(
                df.set_index("timestamp")[["precipitation_mm"]],
                color="#3b8bd4",
                height=300,
            )

        with tab_wind:
            st.line_chart(
                df.set_index("timestamp")[["wind_speed_kmh"]],
                color="#1d9e75",
                height=300,
            )

        with tab_raw:
            st.dataframe(
                df[["timestamp", "temperature_c", "humidity_pct",
                    "precipitation_mm", "wind_speed_kmh", "solar_rad_wm2"]].tail(48),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(f"Showing last 48 rows of {len(df)} total")


def render_aq():
    st.markdown("### 🌬️ Air Quality — Atmo Nouvelle-Aquitaine")
    st.caption("Source: `opendata.atmo-na.org` · Daily measurements · PM2.5, PM10, NO2, O3")

    status = get_collector_status("air_quality")

    col1, col2, col3 = st.columns(3)
    col1.metric("Status", "✅ Data available" if status["status"] == "ok" else "⏳ Not yet implemented")
    col2.metric("Records", status["rows"] if status["rows"] else "—")
    col3.metric("Last fetch", status["latest"] if status["latest"] else "—")

    st.info("Air quality collector coming in next phase. Dataset: `gir_polluant_jour_1`")


def _latest_csv_for_zone(domain_dir, zone_slug):
    """Like get_collector_status, but scoped to files saved for a specific zone
    — collector output files are named e.g. `car_traffic_<zone_slug>_<stamp>.csv`."""
    if not os.path.exists(domain_dir):
        return None
    files = [f for f in os.listdir(domain_dir) if f.endswith(".csv") and f"_{zone_slug}_" in f]
    if not files:
        return None
    return max([os.path.join(domain_dir, f) for f in files], key=os.path.getmtime)


def render_traffic():
    from datetime import datetime
    from zones import ZONES, DEFAULT_ZONE

    zone_options = list(ZONES.keys())
    zone_insee = st.selectbox(
        "Zone", options=zone_options, index=zone_options.index(DEFAULT_ZONE),
        format_func=lambda k: ZONES[k]["name"], key="traffic_zone",
    )
    zone_name = ZONES[zone_insee]["name"]
    zone_slug = zone_name.lower()

    st.markdown(f"### 🚗 Car Traffic — {zone_name}")
    st.caption(
        "Source: `opendata.bordeaux-metropole.fr` · Live sensor counts (`pc_capte_p`) · "
        "Daily historical (`pc_capte_p_histo_jour`)"
    )

    traffic_dir = os.path.join(DATA_DIR, "traffic")
    latest_path = _latest_csv_for_zone(traffic_dir, zone_slug)
    if latest_path:
        try:
            rows = len(pd.read_csv(latest_path))
        except Exception:
            rows = 0
        status = {
            "status": "ok", "rows": rows, "latest_path": latest_path,
            "latest": datetime.fromtimestamp(os.path.getmtime(latest_path)).strftime("%Y-%m-%d %H:%M"),
        }
    else:
        status = {"status": "no_data", "rows": 0, "latest": None}

    col1, col2, col3 = st.columns(3)
    col1.metric("Status", "✅ Data available" if status["status"] == "ok" else "❌ No data yet")
    col2.metric("Records", status["rows"] if status["rows"] else "—")
    col3.metric("Last fetch", status["latest"] if status["latest"] else "—")

    col_btn, col_days = st.columns([1, 2])
    with col_days:
        days = st.slider("Days of history to fetch", 7, 365, 90, key="traffic_days")
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch = st.button("⬇️ Fetch traffic history", key="fetch_traffic", use_container_width=True)

    if fetch:
        with st.spinner(f"Fetching sensors + history for {zone_name}..."):
            try:
                from collectors.traffic_collector import collect
                df = collect(zone_insee=zone_insee, days_back=days, save=True)
                if df.empty:
                    st.warning("No records returned — check the dataset manually: "
                               "opendata.bordeaux-metropole.fr/explore/dataset/pc_capte_p_histo_jour/")
                else:
                    st.success(f"✅ Fetched {len(df)} records")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    if status["status"] == "ok":
        df = pd.read_csv(status["latest_path"])
        st.divider()
        st.caption(f"Loaded: `{os.path.basename(status['latest_path'])}` · {len(df)} rows · {df['ident'].nunique() if 'ident' in df.columns else '?'} sensors")

        date_col = "Date de comptage" if "Date de comptage" in df.columns else None
        if date_col and "comptage_5m" in df.columns:
            df[date_col] = pd.to_datetime(df[date_col])
            daily_total = df.groupby(date_col)["comptage_5m"].sum()
            st.line_chart(daily_total, color="#e8593c", height=300)
            st.caption("Sum of daily vehicle counts across all sensors in the zone")

        with st.expander("📋 Raw data"):
            display_df = df.tail(200).rename(columns={
                "Date de comptage": "Date",
                "ident": "Sensor ID",
                "zone": "Sensor Zone Code",
                "type": "Sensor Type",
                "comptage_5m": "Vehicle Count",
                "Geo Point": "Coordinates",
                "cdate": "Sensor Installed",
            }).drop(columns=["gid"], errors="ignore")
            column_order = [c for c in ["Date", "Sensor ID", "Vehicle Count", "Coordinates", "Sensor Type", "Sensor Zone Code", "Sensor Installed"] if c in display_df.columns]
            st.dataframe(display_df[column_order], use_container_width=True, hide_index=True)
            st.caption(f"Showing last 200 rows of {len(df)} total")


def render():
    st.caption("Collect real data from external APIs and visualize results")

    # Summary status bar
    domains = ["weather", "air_quality", "traffic"]
    statuses = {d: get_collector_status(d) for d in domains}
    active = sum(1 for s in statuses.values() if s["status"] == "ok")
    total_rows = sum(s["rows"] for s in statuses.values())

    c1, c2, c3 = st.columns(3)
    c1.metric("Active collectors", f"{active} / {len(domains)}")
    c2.metric("Total records collected", total_rows)
    c3.metric("Storage", "data/ folder")

    st.divider()

    # Tabs per collector
    tab1, tab2, tab3 = st.tabs(["🌤️ Weather", "🌬️ Air Quality", "🚗 Traffic"])

    with tab1:
        render_weather()
    with tab2:
        render_aq()
    with tab3:
        render_traffic()
