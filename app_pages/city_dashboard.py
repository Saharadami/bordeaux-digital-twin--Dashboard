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
from emissions.bus_emissions_engine import compute_bus_emissions_for_zone
from emissions.emission_factors import BUS_EMISSION_FACTORS_G_PER_KM, ENERGY_MJ_PER_KM
from forecasting.traffic_forecasting_engine import forecast_traffic
from emissions.spatial_heatmap_data import car_heatmap_points, bus_emission_lines, POLLUTANTS

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MOBILITY_DIR = os.path.join(DATA_DIR, "mobility")
TRAFFIC_DIR = os.path.join(DATA_DIR, "traffic")

# ── Palette (dataviz skill reference palette, light mode) ──
COLOR_BIKE = "#1baf7a"    # categorical slot 2 — aqua
COLOR_CAR = "#2a78d6"     # categorical slot 1 — blue
COLOR_BUS = "#e0791e"     # categorical slot 3 — amber
COLOR_ENERGY = "#4a3aa7"  # categorical slot 5 — violet (kept off Bus's orange/Car's blue)
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"

# Network-wide totals from TBM's live GTFS static feed (routes.txt, route_type
# 0=tram/3=bus), checked 2026-07-07 — used only to give the per-zone line
# counts shown below some context ("N of ~TOTAL"). Approximate: TBM revises
# its GTFS feed periodically, so these may drift slightly over time.
TOTAL_TBM_TRAM_ROUTES = 6
TOTAL_TBM_BUS_ROUTES = 194

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
    "tram": {
        "label": "Tram", "icon": "🚋", "kind": "note",
        "note": "Tram is **live + static only** — TBM's open data does not expose "
                "historical vehicle positions or ridership for tram lines. See the live map above.",
    },
    "bus": {
        "label": "Bus", "icon": "🚌", "kind": "bus_emission",
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


def _compact_signed(n, unit):
    """None for ~zero so st.metric shows no delta pill at the scenario baseline
    — a literal "+0" would still read as a (red, under delta_color=inverse)
    positive change, which is misleading for "no change"."""
    if abs(n) < 1e-9:
        return None
    sign = "+" if n >= 0 else "-"
    return f"{sign}{_compact(abs(n))} {unit}"


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


# ColorBrewer "YlOrRd" sequential ramp — shared by the Car heat layer's
# gradient and the Bus lines' per-line color, so both encode intensity on the
# exact same scale (this tab is about *how much*, not *which line is which*,
# so official route colors are deliberately not used here).
_HEAT_RAMP = [
    (0.00, (255, 255, 178)),  # #ffffb2
    (0.25, (254, 204, 92)),   # #fecc5c
    (0.50, (253, 141, 60)),   # #fd8d3c
    (0.75, (240, 59, 32)),    # #f03b20
    (1.00, (189, 0, 38)),     # #bd0026
]


def _yellow_red_hex(frac):
    frac = max(0.0, min(1.0, frac))
    for (f0, c0), (f1, c1) in zip(_HEAT_RAMP, _HEAT_RAMP[1:]):
        if f0 <= frac <= f1:
            t = (frac - f0) / (f1 - f0) if f1 > f0 else 0.0
            rgb = tuple(round(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))
            return "#{:02x}{:02x}{:02x}".format(*rgb)
    return "#{:02x}{:02x}{:02x}".format(*_HEAT_RAMP[-1][1])


def _heatmap_html(car_points, bus_lines, boundary_geojson, bounds, pollutant_label, unit):
    max_car = max((p["intensity"] for p in car_points), default=1.0) or 1.0
    bus_values = [ln["value"] for ln in bus_lines]
    min_bus, max_bus = (min(bus_values), max(bus_values)) if bus_values else (0.0, 1.0)

    bus_features = []
    for ln in bus_lines:
        frac = (ln["value"] - min_bus) / (max_bus - min_bus) if max_bus > min_bus else 0.5
        bus_features.append({
            "code": ln["code"], "coords": ln["coords"], "value": ln["value"],
            "color": _yellow_red_hex(frac),
        })

    heat_points = [[p["lat"], p["lon"], p["intensity"]] for p in car_points]

    template = """<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<link href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" rel="stylesheet"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
html, body { height:100%; }
#map { width:100%; height:480px; background:#0f1923; }
.leaflet-popup-content-wrapper { background:rgba(15,25,35,0.96) !important; border:1px solid #ffffff33 !important; border-radius:8px !important; color:white !important; }
.leaflet-popup-content { margin:9px 12px !important; font-size:12px !important; }
.leaflet-popup-tip { background:rgba(15,25,35,0.96) !important; }
</style></head>
<body>
<div id="map"></div>
<script>
const HEAT_POINTS = __HEAT_POINTS__;
const MAX_CAR = __MAX_CAR__;
const BUS_FEATURES = __BUS_FEATURES__;
const ZONE_GEOJSON = __ZONE_JSON__;
const BOUNDS = __BOUNDS_JSON__;
const POLLUTANT = "__POLLUTANT__";
const UNIT = "__UNIT__";

const map = L.map('map', { zoomControl: false, center: [44.85, -0.58], zoom: 12 });
L.control.zoom({ position: 'bottomright' }).addTo(map);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO', subdomains: 'abcd', maxZoom: 19,
}).addTo(map);

if (ZONE_GEOJSON) {
    L.geoJSON(ZONE_GEOJSON, {
        style: { color: '#5dade2', weight: 2, dashArray: '6,4', fillColor: '#2980b9', fillOpacity: 0.08 },
    }).addTo(map);
}

BUS_FEATURES.forEach(function (f) {
    const line = L.polyline(f.coords, { color: f.color, weight: 4, opacity: 0.85 }).addTo(map);
    line.bindPopup('<b>Bus line ' + f.code + '</b><br/>' + Math.round(f.value).toLocaleString() + ' ' + UNIT + ' ' + POLLUTANT + '/day');
});

// Streamlit's st.tabs() renders every tab's components on every script run —
// hidden tabs are just display:none, not unmounted — so this iframe can load
// while genuinely 0x0 (whichever tab happens to be active first). Calling
// fitBounds()/adding the heat layer against a 0x0 container gives a bogus
// zoom (or a canvas the browser refuses to draw to), and invalidateSize()
// alone does not fix a *wrong* zoom already chosen from bad dimensions — so
// wait for a real, non-zero size via ResizeObserver (fires exactly when the
// tab becomes visible, however long that takes) before doing any of this.
let mapSetupDone = false;
function setupMapView() {
    if (mapSetupDone) return;
    const size = map.getSize();
    if (size.x === 0 || size.y === 0) return;
    mapSetupDone = true;
    map.invalidateSize();
    if (BOUNDS) {
        map.fitBounds([[BOUNDS[0][1], BOUNDS[0][0]], [BOUNDS[1][1], BOUNDS[1][0]]], { padding: [30, 30], animate: false });
    }
    if (HEAT_POINTS.length) {
        L.heatLayer(HEAT_POINTS, {
            radius: 28, blur: 20, maxZoom: 16, max: MAX_CAR,
            gradient: { 0.0: '#ffffb2', 0.25: '#fecc5c', 0.5: '#fd8d3c', 0.75: '#f03b20', 1.0: '#bd0026' },
        }).addTo(map);
    }
}

map.whenReady(function () {
    setupMapView();
    if (!mapSetupDone) {
        const ro = new ResizeObserver(function () {
            setupMapView();
            if (mapSetupDone) ro.disconnect();
        });
        ro.observe(document.getElementById('map'));
    }
});
</script>
</body></html>"""

    html = template.replace("__HEAT_POINTS__", json.dumps(heat_points))
    html = html.replace("__MAX_CAR__", json.dumps(max_car))
    html = html.replace("__BUS_FEATURES__", json.dumps(bus_features))
    html = html.replace("__ZONE_JSON__", json.dumps(boundary_geojson) if boundary_geojson else "null")
    html = html.replace("__BOUNDS_JSON__", json.dumps(bounds) if bounds else "null")
    html = html.replace("__POLLUTANT__", pollutant_label)
    html = html.replace("__UNIT__", unit)
    return html


def _render_heatmap_section(zone_insee, zone_name):
    """Spatial emission intensity — Car sensors as a heat layer (leaflet.heat,
    via CDN, no new Python dependency), Bus lines as colored polylines on the
    same yellow-to-red scale. Both reuse already-computed pollutant totals
    (emissions_engine.py / bus_emissions_engine.py) joined with geometry
    already used elsewhere — see emissions/spatial_heatmap_data.py."""
    col_pollutant, col_car, col_bus = st.columns([2, 1, 1])
    with col_pollutant:
        pollutant = st.selectbox(
            "Pollutant", options=list(POLLUTANTS), index=0, key="dash_heatmap_pollutant",
        )
    with col_car:
        show_car = st.checkbox("🚗 Show Car Heatmap", value=True, key="dash_heatmap_show_car")
    with col_bus:
        show_bus = st.checkbox("🚌 Show Bus Lines", value=True, key="dash_heatmap_show_bus")

    if not show_car and not show_bus:
        st.info("Select at least one layer to display.")
        return

    st.caption(
        "Since CO2/NOx/PM are all proportional to the same vehicle count, the "
        "relative pattern (which roads/lines are worst) is identical for all three "
        "pollutants — only the absolute values differ."
    )
    unit = "kg" if pollutant == "CO2" else "g"

    car_points = []
    if show_car:
        car_latest = _latest_csv(TRAFFIC_DIR, zone_slug=zone_name.lower())
        car_points = car_heatmap_points(car_latest, pollutant) if car_latest else []

    bus_lines = []
    if show_bus:
        bus_lines = bus_emission_lines(zone_insee, pollutant)

    if pollutant == "CO2":
        car_points = [{**p, "intensity": p["intensity"] / 1000} for p in car_points]
        bus_lines = [{**ln, "value": ln["value"] / 1000} for ln in bus_lines]

    if not car_points and not bus_lines:
        st.info(
            f"No car traffic or bus data available yet for {zone_name} — fetch Car "
            f"Traffic data from the Mobility Historical tab first."
        )
        return

    caption_parts = []
    if show_car:
        caption_parts.append(f"**{len(car_points)} car sensors** (average daily {pollutant})")
    if show_bus:
        caption_parts.append(f"**{len(bus_lines)} bus lines** (estimated daily {pollutant})")
    tail = " — same yellow-to-red scale for both, since this shows intensity, not line identity." if show_car and show_bus else ""
    st.caption(" · ".join(caption_parts) + tail)

    boundary = get_zone_boundary(zone_insee)
    bounds = get_zone_bounds(zone_insee)
    html = _heatmap_html(car_points, bus_lines, boundary, bounds, pollutant, unit)
    components.html(html, height=480, scrolling=False)


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


def _bus_line_bar_chart(per_line, color, top_n=14):
    """Same ranked-horizontal-bar style as _sensor_bar_chart, applied to
    per-line estimated daily CO2 (kg) instead of sensor totals."""
    d = pd.DataFrame([
        {"label": f"Line {r['code']}", "co2_kg": r["daily_km"] * BUS_EMISSION_FACTORS_G_PER_KM["CO2"] / 1000}
        for r in per_line
    ]).sort_values("co2_kg", ascending=False).head(top_n)

    bars = alt.Chart(d).mark_bar(
        color=color, size=16, cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
    ).encode(
        y=alt.Y("label:N", sort="-x", title=None,
                axis=alt.Axis(labelLimit=230, labelColor=INK_SECONDARY, domain=False, ticks=False)),
        x=alt.X("co2_kg:Q", title=None,
                axis=alt.Axis(grid=True, gridColor=GRIDLINE, domain=False, tickColor=BASELINE, labelColor=INK_MUTED, format="~s")),
        tooltip=[alt.Tooltip("label:N", title="Line"), alt.Tooltip("co2_kg:Q", title="CO2 (kg/day)", format=",.0f")],
    )
    labels = alt.Chart(d).mark_text(align="left", dx=5, color=INK_SECONDARY, fontSize=11).encode(
        y=alt.Y("label:N", sort="-x"),
        x="co2_kg:Q",
        text=alt.Text("co2_kg:Q", format=",.0f"),
    )
    return (bars + labels).properties(height=max(160, len(d) * 30)).configure_view(strokeWidth=0)


def _energy_share_donut(car_mj, bus_mj):
    """Two-slice donut — Car vs Bus share of combined daily energy. Colored
    per-entity (same blue/amber as everywhere else Car/Bus appear) rather than
    a generic ramp, so identity carries across every chart in this section.
    Only two categories, so color alone is legible, but still direct-labelled
    per the dataviz skill's series-count ladder (1-3 series -> direct-label)."""
    total = car_mj + bus_mj
    d = pd.DataFrame([{"mode": "Car", "mj": car_mj}, {"mode": "Bus", "mj": bus_mj}])
    d["pct_label"] = (d["mj"] / total * 100).round(0).astype(int).astype(str) + "%"

    color_scale = alt.Scale(domain=["Car", "Bus"], range=[COLOR_CAR, COLOR_BUS])
    base = alt.Chart(d).encode(
        theta=alt.Theta("mj:Q", stack=True),
        color=alt.Color("mode:N", scale=color_scale, legend=alt.Legend(title=None, orient="bottom", labelColor=INK_SECONDARY)),
        tooltip=[alt.Tooltip("mode:N", title="Mode"), alt.Tooltip("mj:Q", title="MJ/day", format=",.0f")],
    )
    arc = base.mark_arc(innerRadius=58, outerRadius=104, stroke=SURFACE, strokeWidth=2)
    labels = base.mark_text(radius=128, size=13, color=INK_SECONDARY, fontWeight=600).encode(text="pct_label:N")
    return (arc + labels).properties(height=240).configure_view(strokeWidth=0)


def _energy_intensity_bar(car_mj_per_km, bus_mj_per_km):
    """Two-bar horizontal comparison — energy intensity (MJ/km), same
    ranked-bar style as the other charts, colored per-entity so it reads as
    the deliberate counterpoint to the donut beside it: Car dominates total
    share, Bus dominates per-km intensity."""
    d = pd.DataFrame([{"mode": "Car", "mj_per_km": car_mj_per_km}, {"mode": "Bus", "mj_per_km": bus_mj_per_km}])
    color_scale = alt.Scale(domain=["Car", "Bus"], range=[COLOR_CAR, COLOR_BUS])

    bars = alt.Chart(d).mark_bar(size=34, cornerRadiusTopRight=4, cornerRadiusBottomRight=4).encode(
        y=alt.Y("mode:N", sort=None, title=None,
                axis=alt.Axis(labelColor=INK_SECONDARY, domain=False, ticks=False, labelFontSize=13)),
        x=alt.X("mj_per_km:Q", title=None,
                axis=alt.Axis(grid=True, gridColor=GRIDLINE, domain=False, tickColor=BASELINE, labelColor=INK_MUTED)),
        color=alt.Color("mode:N", scale=color_scale, legend=None),
        tooltip=[alt.Tooltip("mode:N", title="Mode"), alt.Tooltip("mj_per_km:Q", title="MJ/km", format=".2f")],
    )
    labels = alt.Chart(d).mark_text(align="left", dx=6, color=INK_SECONDARY, fontSize=12).encode(
        y=alt.Y("mode:N", sort=None), x="mj_per_km:Q", text=alt.Text("mj_per_km:Q", format=".2f"),
    )
    return (bars + labels).properties(height=150).configure_view(strokeWidth=0)


def _forecast_chart(df, color):
    """Solid line for actual history, dashed line for the 7-day forecast, and
    a shaded uncertainty band around the forecast only (history is observed,
    not uncertain). The two line segments share their first/last point (the
    engine duplicates the last actual day as the first forecast row) so they
    connect with no visual gap."""
    actual = df[df["kind"] == "actual"]
    forecast = df[df["kind"] == "forecast"]

    band = alt.Chart(forecast).mark_area(opacity=0.15, color=color).encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("lower:Q", title=None),
        y2=alt.Y2("upper:Q"),
    )
    actual_line = alt.Chart(actual).mark_line(color=color, strokeWidth=2).encode(
        x=alt.X("date:T", title=None,
                axis=alt.Axis(grid=False, domainColor=BASELINE, tickColor=BASELINE, labelColor=INK_MUTED)),
        y=alt.Y("value:Q", title=None,
                axis=alt.Axis(grid=True, gridColor=GRIDLINE, domain=False, tickColor=BASELINE, labelColor=INK_MUTED, format="~s")),
        tooltip=[alt.Tooltip("date:T", title="Date", format="%b %d, %Y"), alt.Tooltip("value:Q", title="Actual", format=",.0f")],
    )
    forecast_line = alt.Chart(forecast).mark_line(color=color, strokeWidth=2, strokeDash=[5, 4]).encode(
        x="date:T", y="value:Q",
        tooltip=[alt.Tooltip("date:T", title="Date", format="%b %d, %Y"), alt.Tooltip("value:Q", title="Forecast", format=",.0f")],
    )
    return (band + actual_line + forecast_line).properties(height=280).configure_view(strokeWidth=0)


def _render_forecast_section(zone_insee, zone_name):
    """Rule-based 7-day traffic forecast — linear trend + day-of-week OLS
    regression, no ML (see forecasting/traffic_forecasting_engine.py). Only
    Car Traffic and Bike have daily historical data to forecast from."""
    forecast_mode_keys = [k for k in ("car", "bike") if k in MODES]
    mode_key = st.selectbox(
        "Mode", options=forecast_mode_keys,
        format_func=lambda k: f"{MODES[k]['icon']} {MODES[k]['label']}",
        key="dash_forecast_mode",
    )
    cfg = MODES[mode_key]
    latest = _latest_csv(cfg["dir"], zone_slug=zone_name.lower())
    if not latest:
        st.info(
            f"No {cfg['label'].lower()} data for {zone_name} yet — fetch it from the "
            f"{cfg['icon']} {cfg['label']} mode in Mobility Historical first."
        )
        return

    try:
        result = forecast_traffic(latest, cfg["date_col"], cfg["value_col"], horizon_days=7)
    except ValueError as e:
        st.info(str(e))
        return

    n_history_days = result.attrs.get("n_history_days", 0)
    st.caption(
        f"Simple linear model (trend + day-of-week), fit on **{n_history_days} days** of "
        f"history for {zone_name} · 7-day forecast, shaded band ≈ 90% uncertainty range — "
        f"not a calibrated prediction, just a rule-based projection from limited data."
    )

    st.markdown(f"**{cfg['label']} — daily total, actual vs 7-day forecast**")
    st.altair_chart(_forecast_chart(result, cfg["color"]), use_container_width=True)

    with st.expander("📋 Forecast values"):
        show = result[result["kind"] == "forecast"].iloc[1:].copy()
        show["date"] = show["date"].dt.strftime("%Y-%m-%d (%a)")
        show = show.rename(columns={
            "date": "Date", "value": "Forecast", "lower": "Lower bound", "upper": "Upper bound",
        })
        st.dataframe(
            show[["Date", "Forecast", "Lower bound", "Upper bound"]].round(1),
            use_container_width=True, hide_index=True,
        )


def _render_map_section(zone_insee):
    zone_name = ZONES[zone_insee]["name"]
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
        show_tram = st.checkbox(
            f"🚋 Tram ({len(tram_keys)} of ~{TOTAL_TBM_TRAM_ROUTES} TBM tram lines serving {zone_name})",
            value=True, key=f"dash_show_tram_{zone_insee}",
        )
        tram_codes = [lines_data[k]["code"] for k in tram_keys]
        tram_sel = st.multiselect(
            "Tram lines", options=tram_codes, default=tram_codes[:1],
            key=f"dash_tram_lines_{zone_insee}", disabled=not show_tram, format_func=lambda c: f"Line {c}",
        ) if show_tram else []
    with col_b:
        show_bus = st.checkbox(
            f"🚌 Bus ({len(bus_keys)} of ~{TOTAL_TBM_BUS_ROUTES} TBM bus routes serving {zone_name})",
            value=True, key=f"dash_show_bus_{zone_insee}",
        )
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
    st.caption(
        "NOx factor: diesel passenger car average (Euro 5-era EU fleet) — not "
        "blended with petrol share, which was not available from the source. "
        "PM factor: still pending verification — attempted HBEFA/CITEPA and the "
        "EMEP Guidebook PDF extraction, no reliable average found yet."
    )

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


def _render_bus_emission_section(zone_insee, zone_name):
    """Rule-based CO2/NOx/PM estimate for the zone's bus network on one
    representative weekday — from the *scheduled* GTFS timetable (trips.txt +
    calendar.txt), not live vehicle counts. See emissions/bus_emissions_engine.py."""
    result = compute_bus_emissions_for_zone(zone_insee)
    if result is None:
        st.info(f"No bus lines are mapped for {zone_name} yet — see the live map above.")
        return
    if result["total_km"] <= 0:
        st.info("No scheduled weekday bus trips found for this zone's lines.")
        return

    st.caption(
        f"Based on the official GTFS schedule for a typical weekday (Mon–Fri service) — "
        f"a single-day estimate, not a historical trend. Showing "
        f"**{len(result['per_line'])} of ~{TOTAL_TBM_BUS_ROUTES} TBM bus routes** serving {zone_name}."
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Estimated daily CO₂", f"{_compact(result['CO2_g'] / 1000)} kg")
    c2.metric("Estimated daily NOx", f"{_compact(result['NOx_g'])} g")
    c3.metric("Estimated daily PM", f"{_compact(result['PM_g'])} g")

    # Comparison against this zone's Car Traffic emission estimate, if that
    # section has already fetched/computed data for the same zone — silently
    # omitted (not an error) when no car traffic CSV exists yet for this zone.
    car_latest = _latest_csv(TRAFFIC_DIR, zone_slug=zone_name.lower())
    if car_latest:
        car_df = compute_emissions(car_latest)
        if not car_df.empty:
            period_options = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90, "All available": None}
            period_label = st.session_state.get("dash_emission_period", "Last 90 days")
            days_back = period_options.get(period_label)
            if days_back:
                cutoff = car_df["date"].max() - pd.Timedelta(days=days_back)
                car_df = car_df[car_df["date"] >= cutoff]
            car_co2_g = car_df["CO2_g"].sum()
            n_days = car_df["date"].dt.floor("D").nunique()
            if car_co2_g > 0 and n_days > 0:
                car_daily_co2_g = car_co2_g / n_days
                pct = result["CO2_g"] / car_daily_co2_g * 100
                st.caption(
                    f"≈ **{pct:.1f}%** of this zone's estimated daily car traffic CO₂"
                )

    st.markdown("**Bus lines by estimated daily CO₂**")
    st.altair_chart(_bus_line_bar_chart(result["per_line"], COLOR_BUS), use_container_width=True)

    st.markdown("**Per-line breakdown**")
    rows = [{
        "Line": r["code"],
        "Daily trips": r["daily_trips"],
        "Route length (km)": round(r["length_km"], 2),
        "Daily km": round(r["daily_km"], 1),
        "Energy (MJ)": round(r["daily_km"] * ENERGY_MJ_PER_KM["bus"], 1),
        "Energy per Trip (MJ)": (
            round(r["daily_km"] * ENERGY_MJ_PER_KM["bus"] / r["daily_trips"], 2) if r["daily_trips"] > 0 else 0
        ),
        "Share of total emission": f"{r['share_pct']:.1f}%",
    } for r in result["per_line"]]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_energy_section(zone_insee, zone_name):
    """Combined Car vs Bus daily energy consumption (MJ) for this zone — see
    emission_factors.ENERGY_MJ_PER_KM. This is a cross-mode comparison (not
    specific to Car or Bus), so it renders identically whichever mode it's
    called from — see the two call sites in _render_historical_section."""
    car_latest = _latest_csv(TRAFFIC_DIR, zone_slug=zone_name.lower())
    bus_result = compute_bus_emissions_for_zone(zone_insee)
    if not car_latest or bus_result is None or bus_result["total_km"] <= 0:
        st.info(
            "Energy Consumption needs both Car Traffic data and a mapped bus network "
            "for this zone — fetch Car Traffic data above if you haven't yet."
        )
        return

    car_df = compute_emissions(car_latest)
    if car_df.empty:
        st.info("No usable car traffic data to estimate energy from.")
        return
    period_options = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90, "All available": None}
    period_label = st.session_state.get("dash_emission_period", "Last 90 days")
    days_back = period_options.get(period_label)
    if days_back:
        cutoff = car_df["date"].max() - pd.Timedelta(days=days_back)
        car_df = car_df[car_df["date"] >= cutoff]
    n_days = car_df["date"].dt.floor("D").nunique()
    if car_df.empty or n_days == 0:
        st.info("No car traffic data in the selected period to estimate energy from.")
        return

    car_daily_mj = car_df["Energy_MJ"].sum() / n_days
    bus_daily_mj = bus_result["Energy_MJ"]
    combined_mj = car_daily_mj + bus_daily_mj

    st.divider()
    col_diagram, col_info = st.columns([20, 1])
    with col_diagram:
        st.markdown(
            f'<div style="text-align:center; font-size:17px; font-weight:600; '
            f'color:{INK_SECONDARY}; padding:6px 0 2px 0;">'
            f'🚗🚌 Traffic Count &nbsp;→&nbsp; ⛽ Energy Consumption &nbsp;→&nbsp; 🌫️ CO₂ / NOx / PM'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col_info:
        with st.popover("ℹ️"):
            st.write(
                "This Traffic → Energy → Emissions pathway extends the Mobility → generates "
                "→ AirQuality relationship already documented in the project's Ontology (Data "
                "Model & Ontology tab), adding an explicit Energy step in between."
            )

    st.markdown(
        f'#### <span style="color:{COLOR_ENERGY};">⚡ Energy Consumption</span>',
        unsafe_allow_html=True,
    )
    st.caption("Energy factors: ODYSSEE-MURE (car, EU27 2023), independent industry estimates (bus).")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Daily Energy (Car)", f"{_compact(car_daily_mj)} MJ/day")
    c2.metric("Total Daily Energy (Bus)", f"{_compact(bus_daily_mj)} MJ/day")
    c3.metric("Combined Daily Energy", f"{_compact(combined_mj / 1000)} GJ/day")

    col_donut, col_bar = st.columns(2)
    with col_donut:
        st.markdown("**Share of Total Daily Energy**")
        st.altair_chart(_energy_share_donut(car_daily_mj, bus_daily_mj), use_container_width=True)
    with col_bar:
        st.markdown("**Energy Intensity per km**")
        st.altair_chart(
            _energy_intensity_bar(ENERGY_MJ_PER_KM["car"], ENERGY_MJ_PER_KM["bus"]),
            use_container_width=True,
        )

    with st.expander("🔧 What-if Scenarios", expanded=False):
        st.caption("Simple rule-based projections — linear scaling, not a calibrated simulation.")

        st.markdown("**Traffic Change**")
        traffic_pct = st.slider(
            "Traffic Change", min_value=-50, max_value=50, value=0, step=5,
            format="%d%%", key=f"dash_whatif_traffic_{zone_insee}",
        )
        traffic_factor = 1 + traffic_pct / 100

        car_co2_g = car_df["CO2_g"].sum()
        car_nox_g = car_df["NOx_g"].sum()
        car_pm_g = car_df["PM_g"].sum()
        car_energy_mj = car_df["Energy_MJ"].sum()

        t1, t2, t3, t4 = st.columns(4)
        t1.metric(
            "CO₂", f"{_compact(car_co2_g * traffic_factor / 1000)} kg",
            delta=_compact_signed((car_co2_g * traffic_factor - car_co2_g) / 1000, "kg"),
            delta_color="inverse",
        )
        t2.metric(
            "NOx", f"{_compact(car_nox_g * traffic_factor)} g",
            delta=_compact_signed(car_nox_g * traffic_factor - car_nox_g, "g"),
            delta_color="inverse",
        )
        t3.metric(
            "PM", f"{_compact(car_pm_g * traffic_factor)} g",
            delta=_compact_signed(car_pm_g * traffic_factor - car_pm_g, "g"),
            delta_color="inverse",
        )
        t4.metric(
            "Energy", f"{_compact(car_energy_mj * traffic_factor)} MJ",
            delta=_compact_signed(car_energy_mj * traffic_factor - car_energy_mj, "MJ"),
            delta_color="inverse",
        )

        st.divider()

        st.markdown("**Bus Fleet Electrification**")
        electrification_pct = st.slider(
            "Bus Fleet Electrification", min_value=0, max_value=100, value=0, step=10,
            format="%d%%", key=f"dash_whatif_electrification_{zone_insee}",
        )
        remaining_factor = 1 - electrification_pct / 100

        bus_co2_g = bus_result["CO2_g"]
        bus_nox_g = bus_result["NOx_g"]
        bus_pm_g = bus_result["PM_g"]

        b1, b2, b3 = st.columns(3)
        b1.metric(
            "Bus CO₂", f"{_compact(bus_co2_g * remaining_factor / 1000)} kg",
            delta=_compact_signed((bus_co2_g * remaining_factor - bus_co2_g) / 1000, "kg"),
            delta_color="inverse",
        )
        b2.metric(
            "Bus NOx", f"{_compact(bus_nox_g * remaining_factor)} g",
            delta=_compact_signed(bus_nox_g * remaining_factor - bus_nox_g, "g"),
            delta_color="inverse",
        )
        b3.metric(
            "Bus PM", f"{_compact(bus_pm_g * remaining_factor)} g",
            delta=_compact_signed(bus_pm_g * remaining_factor - bus_pm_g, "g"),
            delta_color="inverse",
        )


def _render_historical_section(zone_insee, zone_name):
    mode_key = st.selectbox(
        "Mode", options=list(MODES.keys()),
        format_func=lambda k: f"{MODES[k]['icon']} {MODES[k]['label']}",
        key="dash_hist_mode",
    )
    cfg = MODES[mode_key]

    if cfg["kind"] == "bus_emission":
        _render_bus_emission_section(zone_insee, zone_name)
        _render_energy_section(zone_insee, zone_name)
        return

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
        _render_energy_section(zone_insee, zone_name)


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

    tab_map, tab_hist, tab_forecast, tab_heatmap = st.tabs([
        "🚋 Tram Live Map", "📊 Mobility Historical", "🔮 Forecast & Simulation", "🔥 Emission Heatmap",
    ])
    with tab_map:
        _render_map_section(zone_insee)
    with tab_hist:
        _render_historical_section(zone_insee, zone_name)
    with tab_forecast:
        _render_forecast_section(zone_insee, zone_name)
    with tab_heatmap:
        _render_heatmap_section(zone_insee, zone_name)
