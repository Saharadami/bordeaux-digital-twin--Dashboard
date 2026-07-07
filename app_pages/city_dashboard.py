"""
City Dashboard — Bordeaux Urban Digital Twin
One page per zone: live transit map on top, historical mode trends below.
Add a zone in zones.py and it shows up in the selector automatically.
"""

import os
import json
import pandas as pd
import altair as alt
import streamlit as st
import streamlit.components.v1 as components

from zones import ZONES, DEFAULT_ZONE
from geo_utils import get_zone_boundary, get_zone_bounds
from app_pages.simulation import (
    load_lines_data, fetch_raw_vehicles, build_matched_vehicles,
    build_route_geojson, build_stops_geojson, build_vehicles_geojson,
    build_html as build_map_html, MODE_ICON,
)
from emissions.emissions_engine import compute_emissions, OUTLIER_MEDIAN_MULTIPLIER

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MOBILITY_DIR = os.path.join(DATA_DIR, "mobility")
TRAFFIC_DIR = os.path.join(DATA_DIR, "traffic")

# ── Palette (dataviz skill reference palette, light mode) ──
COLOR_BIKE = "#1baf7a"    # categorical slot 2 — aqua
COLOR_CAR = "#2a78d6"     # categorical slot 1 — blue
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"

MODES = {
    "bike": {
        "label": "Bike", "icon": "🚴", "kind": "chart", "unit": "trips",
        "dir": MOBILITY_DIR, "color": COLOR_BIKE,
        "date_col": "datedebut", "value_col": "comptage_1h", "label_col": "libelle",
        "collector": "collectors.mobility_collector",
        "source_note": "`pc_velo_p` — hourly bike sensor counts, one row per sensor per hour",
    },
    "car": {
        "label": "Car Traffic", "icon": "🚗", "kind": "chart", "unit": "vehicles",
        "dir": TRAFFIC_DIR, "color": COLOR_CAR,
        "date_col": "Date de comptage", "value_col": "comptage_5m", "label_col": None,
        "collector": "collectors.traffic_collector",
        "source_note": "`pc_capte_p_histo_jour` — daily sensor counts, one row per sensor per day",
    },
    "transit": {
        "label": "Tram & Bus", "icon": "🚋", "kind": "note",
        "note": "Tram and bus are **live + static only** — TBM's open data does not "
                "expose historical vehicle positions or ridership. See the live map above.",
    },
    "pedestrian": {
        "label": "Pedestrians", "icon": "🚶", "kind": "note", "note": None,  # filled per-zone at render time
    },
    "moto": {
        "label": "Moto / Scooter", "icon": "🛵", "kind": "note",
        "note": "No public traffic dataset for motorcycles or shared scooters was found "
                "on Bordeaux Métropole's open data portal (only `st_freefloating_s`, which "
                "is parking-zone locations, not traffic counts). Needs operator-side data "
                "(e.g. Lime/Tier GBFS feeds) — flagged for follow-up research.",
    },
}


def _latest_csv(folder, zone_slug=None):
    if not os.path.exists(folder):
        return None
    files = [f for f in os.listdir(folder) if f.endswith(".csv")]
    if zone_slug:
        files = [f for f in files if f"_{zone_slug}_" in f]
    if not files:
        return None
    return max([os.path.join(folder, f) for f in files], key=os.path.getmtime)


def _compact(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:.0f}"


def _load_sensor_summary(mode_key, zone_insee, days_back=None):
    """Per-sensor totals for the period — the street/location detail a single
    zone-wide daily sum throws away. Returns (DataFrame[ident,label,lat,lon,total],
    filename) sorted by total descending, or (None, filename) if nothing to show."""
    cfg = MODES[mode_key]
    zone_slug = ZONES[zone_insee]["name"].lower()
    latest = _latest_csv(cfg["dir"], zone_slug=zone_slug)
    if not latest:
        return None, None
    filename = os.path.basename(latest)

    df = pd.read_csv(latest)
    df[cfg["date_col"]] = pd.to_datetime(df[cfg["date_col"]], utc=True, errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=[cfg["date_col"], "Geo Point", "ident", cfg["value_col"]])
    if df.empty:
        return None, filename

    if days_back:
        cutoff = df[cfg["date_col"]].max() - pd.Timedelta(days=days_back)
        df = df[df[cfg["date_col"]] >= cutoff]
        if df.empty:
            return None, filename

    geo = df["Geo Point"].astype(str).str.split(",", n=1, expand=True)
    df["_lat"] = pd.to_numeric(geo[0], errors="coerce")
    df["_lon"] = pd.to_numeric(geo[1], errors="coerce")
    df = df.dropna(subset=["_lat", "_lon"])

    label_col = cfg.get("label_col")
    df["_label"] = df[label_col] if label_col and label_col in df.columns else df["ident"]

    summary = df.groupby("ident").agg(
        label=("_label", "first"),
        lat=("_lat", "first"),
        lon=("_lon", "first"),
        total=(cfg["value_col"], "sum"),
    ).reset_index()
    summary = summary.sort_values("total", ascending=False).reset_index(drop=True)
    return summary, filename


def _sensor_map_html(summary_df, color):
    """Small Leaflet map, one circle per sensor, radius ~ sqrt(total) so area
    (not radius) scales with volume — a fair perceptual encoding."""
    totals = summary_df["total"]
    min_t, max_t = float(totals.min()), float(totals.max())

    def radius(v):
        if max_t <= min_t:
            return 14.0
        frac = (v - min_t) / (max_t - min_t)
        return 7.0 + (frac ** 0.5) * 20.0

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row.lon, row.lat]},
            "properties": {
                "label": row.label, "total": int(row.total), "radius": round(radius(row.total), 1),
            },
        }
        for row in summary_df.itertuples()
    ]
    geojson = {"type": "FeatureCollection", "features": features}
    lats = [f["geometry"]["coordinates"][1] for f in features]
    lons = [f["geometry"]["coordinates"][0] for f in features]
    bounds = [[min(lons), min(lats)], [max(lons), max(lats)]]

    template = """<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<link href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" rel="stylesheet"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
html, body { height:100%; }
#map { width:100%; height:370px; background:#0f1923; }
.leaflet-popup-content-wrapper { background:rgba(15,25,35,0.96) !important; border:1px solid #ffffff33 !important; border-radius:8px !important; color:white !important; }
.leaflet-popup-content { margin:9px 12px !important; font-size:12px !important; }
.leaflet-popup-tip { background:rgba(15,25,35,0.96) !important; }
</style></head>
<body>
<div id="map"></div>
<script>
const GEOJSON = __GEOJSON__;
const BOUNDS = __BOUNDS__;
const COLOR = "__COLOR__";

const map = L.map('map', { zoomControl: false, center: [44.85, -0.58], zoom: 12 });
L.control.zoom({ position: 'bottomright' }).addTo(map);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO', subdomains: 'abcd', maxZoom: 19,
}).addTo(map);

L.geoJSON(GEOJSON, {
    pointToLayer: (feature, latlng) => {
        const p = feature.properties;
        const m = L.circleMarker(latlng, {
            radius: p.radius, color: '#ffffff', weight: 1.5, fillColor: COLOR, fillOpacity: 0.55,
        });
        m.bindPopup('<b>' + p.label + '</b><br/>' + p.total.toLocaleString() + ' total');
        return m;
    },
}).addTo(map);

map.whenReady(function () {
    map.invalidateSize();
    map.fitBounds([[BOUNDS[0][1], BOUNDS[0][0]], [BOUNDS[1][1], BOUNDS[1][0]]], { padding: [24, 24], maxZoom: 16 });
});
</script>
</body></html>"""

    html = template.replace("__GEOJSON__", json.dumps(geojson))
    html = html.replace("__BOUNDS__", json.dumps(bounds))
    html = html.replace("__COLOR__", color)
    return html


def _sensor_bar_chart(summary_df, color, unit, top_n=12):
    """Ranked horizontal bars — magnitude comparison across named locations is
    exactly what a bar chart is for. Thin bars, rounded outer end, direct value
    label at the tip instead of relying on axis ticks alone."""
    d = summary_df.head(top_n).copy()
    d["label_short"] = d["label"].astype(str).str.slice(0, 42)

    bars = alt.Chart(d).mark_bar(
        color=color, size=16, cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
    ).encode(
        y=alt.Y("label_short:N", sort="-x", title=None,
                axis=alt.Axis(labelLimit=230, labelColor=INK_SECONDARY, domain=False, ticks=False)),
        x=alt.X("total:Q", title=None,
                axis=alt.Axis(grid=True, gridColor=GRIDLINE, domain=False, tickColor=BASELINE, labelColor=INK_MUTED, format="~s")),
        tooltip=[alt.Tooltip("label:N", title="Location"), alt.Tooltip("total:Q", title=unit.capitalize(), format=",.0f")],
    )
    labels = alt.Chart(d).mark_text(align="left", dx=5, color=INK_SECONDARY, fontSize=11).encode(
        y=alt.Y("label_short:N", sort="-x"),
        x="total:Q",
        text=alt.Text("total:Q", format=",.0f"),
    )
    return (bars + labels).properties(height=max(160, len(d) * 30)).configure_view(strokeWidth=0)


def _render_map_section(zone_insee):
    lines_data, _all_tram_keys, _all_bus_keys, zone_lines = load_lines_data()
    zl = zone_lines.get(zone_insee, {"tram": [], "bus": []})
    tram_keys, bus_keys = zl["tram"], zl["bus"]

    # Widget keys are namespaced by zone: Streamlit keeps a widget's session_state
    # value across reruns and only intersects it with a new `options` list, it does
    # NOT reapply `default=` when the zone (and therefore options) changes. A
    # zone-specific key forces a fresh widget — and a fresh `default` — per zone.
    # Default to just 1 line per mode (not the full zone list) — keeps the initial
    # map light; the visitor opts into more via the multiselect.
    col_a, col_b = st.columns(2)
    with col_a:
        show_tram = st.checkbox(f"🚋 Tram ({len(tram_keys)} lines here)", value=True, key=f"dash_show_tram_{zone_insee}")
        tram_codes = [lines_data[k]["code"] for k in tram_keys]
        tram_sel = st.multiselect(
            "Tram lines", options=tram_codes, default=tram_codes[:1],
            key=f"dash_tram_lines_{zone_insee}", disabled=not show_tram, format_func=lambda c: f"Line {c}",
        ) if show_tram else []
    with col_b:
        show_bus = st.checkbox(f"🚌 Bus ({len(bus_keys)} lines here)", value=True, key=f"dash_show_bus_{zone_insee}")
        bus_codes = [lines_data[k]["code"] for k in bus_keys]
        bus_sel = st.multiselect(
            "Bus lines", options=bus_codes, default=bus_codes[:1],
            key=f"dash_bus_lines_{zone_insee}", disabled=not show_bus,
        ) if show_bus else []

    selected = [f"tram:{c}" for c in tram_sel] + [f"bus:{c}" for c in bus_sel]
    if not selected:
        st.info("Select at least one line to display the map.")
        return

    route_to_key = {lines_data[k]["route_id"]: k for k in selected}
    raw_vehicles, error = fetch_raw_vehicles(tuple(route_to_key.keys()))

    if error:
        st.error(f"Could not fetch live data: {error}")
        st.info("Make sure `gtfs-realtime-bindings` is installed: `pip install gtfs-realtime-bindings`")
        return

    vehicles = build_matched_vehicles(raw_vehicles or [], lines_data, route_to_key)
    route_geojson = build_route_geojson(selected, lines_data)
    stops_geojson = build_stops_geojson(selected, lines_data)
    vehicles_geojson = build_vehicles_geojson(vehicles)

    boundary = get_zone_boundary(zone_insee)
    bounds = get_zone_bounds(zone_insee)
    html = build_map_html(
        route_geojson, stops_geojson, vehicles_geojson, len(vehicles),
        zone_boundary_geojson=boundary, bounds=bounds,
    )
    components.html(html, height=520, scrolling=False)

    c1, c2, c3 = st.columns(3)
    c1.metric("Lines shown", len(selected))
    c2.metric("Active vehicles", len(vehicles))
    c3.metric("Unique stops", len(stops_geojson["features"]))

    with st.expander("Per-line breakdown & live vehicle list"):
        rows = []
        for key in selected:
            line = lines_data[key]
            n_vehicles_line = sum(1 for v in vehicles if v["line"] == key)
            rows.append({
                "Mode": MODE_ICON[line["mode"]] + " " + line["mode"],
                "Line": line["code"],
                "Stops": len(line["stops"]),
                "Active vehicles now": n_vehicles_line,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if vehicles:
            vrows = [{
                "Vehicle": v["label"], "Mode": v["mode"], "Line": v["code"],
                "Speed (km/h)": v["speed"], "Direction": v["direction"], "Status": v["status"],
            } for v in sorted(vehicles, key=lambda x: x["label"])]
            st.dataframe(pd.DataFrame(vrows), use_container_width=True, hide_index=True)

        st.caption(
            "⚠️ Passenger counts / ridership are not part of TBM's open data — figures "
            "above reflect network structure and live vehicle presence only."
        )

    if st.button("🔄 Refresh live positions"):
        fetch_raw_vehicles.clear()
        st.rerun()


def _render_emission_section(zone_insee, zone_name):
    """Rule-Based CO2/NOx/PM estimate from existing car-traffic data — see
    emission_engine_spec.md. No new data collection: reads the same
    data/traffic/car_traffic_<zone>_*.csv the 'car' mode already fetches."""
    zone_slug = zone_name.lower()
    latest = _latest_csv(TRAFFIC_DIR, zone_slug=zone_slug)
    if not latest:
        st.info(
            f"No car traffic data for {zone_name} yet — fetch it from the "
            f"🚗 Car Traffic mode above first, then come back here."
        )
        return

    df = compute_emissions(latest)
    excluded_sensor_ids = df.attrs.get("excluded_sensor_ids", [])
    if df.empty:
        st.info("No usable rows in the traffic data to estimate emissions from.")
        return

    period_options = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90, "All available": None}
    period_label = st.selectbox("Period", options=list(period_options.keys()), index=2, key="dash_emission_period")
    days_back = period_options[period_label]
    if days_back:
        cutoff = df["date"].max() - pd.Timedelta(days=days_back)
        df = df[df["date"] >= cutoff]
    if df.empty:
        st.info(f"No data in the {period_label.lower()} window.")
        return

    st.caption(
        f"**{df['sensor_id'].nunique()} sensors** in {zone_name} · {period_label.lower()} · "
        f"loaded `{os.path.basename(latest)}`"
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Estimated CO₂", f"{_compact(df['CO2_g'].sum() / 1000)} kg")
    c2.metric("Estimated NOx", f"{_compact(df['NOx_g'].sum())} g")
    c3.metric("Estimated PM", f"{_compact(df['PM_g'].sum())} g")

    daily_co2 = df.groupby(df["date"].dt.floor("D"))["CO2_g"].sum().div(1000).reset_index(name="CO2_kg")
    chart = alt.Chart(daily_co2).mark_bar(color="#8b6f47", size=10).encode(
        x=alt.X("date:T", title=None, axis=alt.Axis(grid=False, domainColor=BASELINE, tickColor=BASELINE, labelColor=INK_MUTED)),
        y=alt.Y("CO2_kg:Q", title=None, axis=alt.Axis(grid=True, gridColor=GRIDLINE, domain=False, tickColor=BASELINE, labelColor=INK_MUTED, format="~s")),
        tooltip=[alt.Tooltip("date:T", title="Date", format="%b %d, %Y"), alt.Tooltip("CO2_kg:Q", title="CO2 (kg)", format=",.0f")],
    ).properties(height=220).configure_view(strokeWidth=0)
    st.markdown("**Estimated daily CO₂ across the zone**")
    st.altair_chart(chart, use_container_width=True)

    if excluded_sensor_ids:
        st.caption(
            f"ℹ️ {len(excluded_sensor_ids)} sensor(s) excluded as statistical outliers "
            f"(daily count > {OUTLIER_MEDIAN_MULTIPLIER}× that day's median across sensors): "
            f"`{', '.join(excluded_sensor_ids)}`"
        )

    with st.expander("📋 Per-sensor / per-day estimate"):
        st.dataframe(
            df.rename(columns={
                "sensor_id": "Sensor ID", "date": "Date", "vehicle_count": "Vehicle Count",
                "CO2_g": "CO2 (g)", "NOx_g": "NOx (g)", "PM_g": "PM (g)",
            }),
            use_container_width=True, hide_index=True,
        )


def _render_historical_section(zone_insee, zone_name):
    mode_key = st.selectbox(
        "Mode", options=list(MODES.keys()),
        format_func=lambda k: f"{MODES[k]['icon']} {MODES[k]['label']}",
        key="dash_hist_mode",
    )
    cfg = MODES[mode_key]

    if cfg["kind"] == "note":
        note = cfg["note"]
        if note is None:  # pedestrian: zone-specific
            note = (
                f"Bordeaux Métropole's pedestrian sensor network (`pc_captp_p`) currently has "
                f"**no sensors inside {zone_name}** — coverage is concentrated in central "
                f"Bordeaux. Will pick up automatically if that changes."
            )
        st.warning(note)
        return

    with st.expander(f"⚙️ Fetch / update {cfg['label'].lower()} data"):
        st.caption(f"Source: {cfg['source_note']} · Zone: {zone_name}")
        days = st.slider("Days of history", 7, 365, 90, key=f"dash_{mode_key}_days")
        if st.button(f"⬇️ Fetch {cfg['label']} history", key=f"dash_fetch_{mode_key}"):
            with st.spinner(f"Fetching {cfg['label'].lower()} history for {zone_name}..."):
                try:
                    mod = __import__(cfg["collector"], fromlist=["collect"])
                    df = mod.collect(zone_insee=zone_insee, days_back=days, save=True)
                    if df.empty:
                        st.warning("No records returned.")
                    else:
                        st.success(f"✅ Fetched {len(df)} records")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    period_options = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90, "All available": None}
    period_label = st.selectbox("Period", options=list(period_options.keys()), index=2, key=f"dash_{mode_key}_period")
    summary_df, filename = _load_sensor_summary(mode_key, zone_insee, period_options[period_label])

    if summary_df is None or summary_df.empty:
        st.info(f"No {cfg['label'].lower()} data yet — open the panel above to fetch it.")
        return

    st.caption(
        f"**{len(summary_df)} sensors** reporting in {zone_name} · {period_label.lower()} · "
        f"busiest: **{summary_df.iloc[0]['label']}** ({_compact(summary_df.iloc[0]['total'])} {cfg['unit']}) · "
        f"loaded `{filename}`"
    )

    col_map, col_bar = st.columns([1, 1])
    with col_map:
        st.markdown(f"**Sensor locations** — circle area ∝ {cfg['unit']}")
        components.html(_sensor_map_html(summary_df, cfg["color"]), height=380, scrolling=False)
    with col_bar:
        st.markdown(f"**Busiest locations** — top {min(12, len(summary_df))} of {len(summary_df)}")
        st.altair_chart(_sensor_bar_chart(summary_df, cfg["color"], cfg["unit"]), use_container_width=True)

    with st.expander("📋 Per-sensor data"):
        st.dataframe(
            summary_df.rename(columns={"label": "Location", "total": f"Total {cfg['unit']}", "ident": "Sensor ID"})
                       [["Location", "Sensor ID", f"Total {cfg['unit']}"]],
            use_container_width=True, hide_index=True,
        )

    if mode_key == "car":
        st.divider()
        st.markdown("#### 🌫️ Estimated Emissions (from this traffic data)")
        st.caption(
            "A rule-based CO₂/NOx/PM estimate computed from the vehicle counts above — "
            "not a separate data source or transport mode."
        )
        _render_emission_section(zone_insee, zone_name)


def render():
    st.markdown(
        '<div style="font-size:19px; font-weight:800; margin-bottom:6px;">📍 Select urban area</div>',
        unsafe_allow_html=True,
    )
    zone_options = list(ZONES.keys())
    zone_insee = st.selectbox(
        "Zone", options=zone_options,
        index=zone_options.index(DEFAULT_ZONE),
        format_func=lambda k: ZONES[k]["name"],
        key="dash_zone",
        label_visibility="collapsed",
    )
    zone_name = ZONES[zone_insee]["name"]

    st.markdown(
        f"""<div style="background:linear-gradient(135deg,#1a1a2e,#2980b9);
            border-radius:12px;padding:18px 26px;margin-bottom:18px;color:white;">
            <div style="font-size:22px;font-weight:bold;">🏙️ {zone_name} — Mobility</div>
            <div style="font-size:12px;opacity:0.9;margin-top:4px;">
                Live transit network (real GPS + map-matching) and historical trends for this zone
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    _render_map_section(zone_insee)
    st.divider()
    st.markdown("### 📊 Historical trends")
    _render_historical_section(zone_insee, zone_name)
