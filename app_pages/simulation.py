import streamlit as st
import streamlit.components.v1 as components
import requests
import json
import os
import sys
import colorsys

sys.path.insert(0, os.path.dirname(__file__))
from map_matching import match_vehicle

GTFS_RT_URL = (
    "https://bdx.mecatran.com/utw/ws/gtfsfeed/vehicles/bordeaux"
    "?apiKey=opendata-bordeaux-metropole-flux-gtfs-rt"
)
STATUS_MAP = {0: "INCOMING_AT", 1: "STOPPED_AT", 2: "IN_TRANSIT_TO"}

MODE_ICON = {"tram": "🚋", "bus": "🚌"}

# Fallback colors, only used if a tram line's GTFS route_color was empty
FALLBACK_TRAM_COLORS = {
    "A": "#831F82", "B": "#E50040", "C": "#D35098",
    "D": "#9262A3", "E": "#967651", "F": "#F08700",
}

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "sim_assets", "transit_lines.json")


def _distinct_color(i):
    """TBM's official bus route_color is shared across many lines (branding by
    service tier, not per-line), so bus lines get a synthetic, evenly-spaced
    color instead — works for any number of lines."""
    hue = (i * 0.618033988749895) % 1.0
    r, g, b = colorsys.hls_to_rgb(hue, 0.55, 0.65)
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))


@st.cache_data(show_spinner=False)
def load_lines_data():
    """Returns (lines_by_key, tram_keys, bus_keys, zone_lines).
    lines_by_key: {"tram:A": {route_id, color, outbound, inbound, stops, mode, code}, "bus:23": {...}, ...}
    zone_lines: {"33522": {"tram": ["tram:B"], "bus": ["bus:4", ...]}, ...}
    """
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    lines_by_key = {}

    tram_keys = []
    for code, line in data.get("tram", {}).items():
        line["mode"] = "tram"
        line["code"] = code
        if not line.get("color"):
            line["color"] = FALLBACK_TRAM_COLORS.get(code, "#e74c3c")
        key = f"tram:{code}"
        lines_by_key[key] = line
        tram_keys.append(key)

    bus_keys = []
    for i, code in enumerate(sorted(data.get("bus", {}).keys())):
        line = data["bus"][code]
        line["mode"] = "bus"
        line["code"] = code
        line["color"] = _distinct_color(i)
        key = f"bus:{code}"
        lines_by_key[key] = line
        bus_keys.append(key)

    zone_lines = {
        insee: {
            "tram": [f"tram:{c}" for c in zl.get("tram", [])],
            "bus": [f"bus:{c}" for c in zl.get("bus", [])],
        }
        for insee, zl in data.get("zone_lines", {}).items()
    }

    return lines_by_key, tram_keys, bus_keys, zone_lines


@st.cache_data(ttl=25, show_spinner=False)
def fetch_raw_vehicles(route_ids_tuple):
    """Poll GTFS-RT and return raw vehicle positions for the given route_ids (server-side, cached 25s)."""
    try:
        from google.transit import gtfs_realtime_pb2
    except ImportError:
        return None, "Missing package: pip install gtfs-realtime-bindings"

    try:
        r = requests.get(GTFS_RT_URL, timeout=15)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
    except Exception as e:
        return None, str(e)

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(r.content)

    route_ids = set(route_ids_tuple)
    raw = []
    for entity in feed.entity:
        if not entity.HasField("vehicle"):
            continue
        v = entity.vehicle
        route_id = v.trip.route_id if v.HasField("trip") else ""
        if route_id not in route_ids:
            continue
        if not v.HasField("position"):
            continue
        raw.append({
            "id":        v.vehicle.id if v.HasField("vehicle") else entity.id,
            "route_id":  route_id,
            "lat":       v.position.latitude,
            "lon":       v.position.longitude,
            "speed_kmh": round(v.position.speed * 3.6, 1) if v.position.HasField("speed") else 0.0,
            "status":    STATUS_MAP.get(v.current_status, "UNKNOWN"),
            "trip_id":   v.trip.trip_id if v.HasField("trip") else "",
        })
    return raw, None


def build_matched_vehicles(raw_vehicles, lines_data, route_to_key):
    """Run map-matching per vehicle, using its own line's route geometry."""
    out = []
    for rv in raw_vehicles:
        key = route_to_key.get(rv["route_id"])
        line = lines_data.get(key)
        if not line:
            continue
        m = match_vehicle(rv["lon"], rv["lat"], line["outbound"], line["inbound"])
        if m is None:
            continue
        out.append({
            "label":       f"{MODE_ICON[line['mode']]}{line['code']} · " + rv["id"].split(":")[-1],
            "line":        key,
            "mode":        line["mode"],
            "code":        line["code"],
            "color":       line["color"],
            "raw_lon":     rv["lon"],
            "raw_lat":     rv["lat"],
            "matched_lon": m["matched_lon"],
            "matched_lat": m["matched_lat"],
            "direction":   m["direction"],
            "offset_m":    round(m["distance_m"], 1),
            "speed":       rv["speed_kmh"],
            "status":      rv["status"],
            "trip":        rv["trip_id"],
        })
    return out


def build_stops_geojson(selected_keys, lines_data):
    """Dedupe stops across selected lines; stops served by 2+ lines are marked as interchanges."""
    stop_lines = {}   # stop_id -> {"name":..., "lat":..., "lon":..., "lines": set()}
    for key in selected_keys:
        code = lines_data[key]["code"]
        for s in lines_data[key]["stops"]:
            entry = stop_lines.setdefault(s["id"], {"name": s["name"], "lat": s["lat"], "lon": s["lon"], "lines": set()})
            entry["lines"].add(code)

    features = []
    for sid, s in stop_lines.items():
        is_interchange = len(s["lines"]) > 1
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
            "properties": {
                "name": s["name"],
                "id": sid,
                "lines": " · ".join(sorted(s["lines"])),
                "interchange": is_interchange,
            },
        })
    return {"type": "FeatureCollection", "features": features}


def build_route_geojson(selected_keys, lines_data):
    features = []
    for key in selected_keys:
        line = lines_data[key]
        for dir_name, coords in [("outbound", line["outbound"]), ("inbound", line["inbound"])]:
            if coords:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {"line": line["code"], "dir": dir_name, "color": line["color"]},
                })
    return {"type": "FeatureCollection", "features": features}


def build_vehicles_geojson(vehicles):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [v["matched_lon"], v["matched_lat"]]},
                "properties": {
                    "label": v["label"], "speed": v["speed"], "status": v["status"],
                    "direction": v["direction"], "trip": v["trip"], "offset": v["offset_m"],
                    "color": v["color"], "line": v["line"],
                },
            }
            for v in vehicles
        ],
    }


def build_html(route_geojson, stops_geojson, vehicles_geojson, n_vehicles,
                center=(-0.58, 44.85), zoom=11.3, zone_boundary_geojson=None, bounds=None):
    """Renders the live map with Leaflet (not MapLibre/Mapbox).

    MapLibre GL JS was tried first (see git history) but its vector-tile /
    GeoJSON worker never completes a single tile inside Streamlit's
    `about:srcdoc` component iframe — confirmed across Chromium and Firefox,
    with every worker-loading strategy (auto-detect, blob URL, same-origin
    static file). Raster tiles load fine in that same iframe (no worker
    needed), and Leaflet — which has no worker dependency for its core
    tile/marker/polyline rendering — works reliably. Trade-off: no 3D
    pitch/tilt or building extrusion (those need vector tiles), but every
    other feature (route lines, stops, live vehicles, popups, zone outline,
    dark/light/satellite toggle) is unaffected.
    """
    route_json = json.dumps(route_geojson)
    stops_json = json.dumps(stops_geojson)
    vehicles_json = json.dumps(vehicles_geojson)
    zone_json = json.dumps(zone_boundary_geojson) if zone_boundary_geojson else "null"
    bounds_json = json.dumps(bounds) if bounds else "null"

    template = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<link href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" rel="stylesheet"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: Arial, sans-serif; background:#0f1923; }
#map { width:100%; height:640px; }
#controls { position:absolute; top:12px; left:12px; z-index:10; display:flex; flex-direction:column; gap:6px; }
.ctrl-btn { background:rgba(20,35,50,0.92); border:1px solid #2980b9; color:white; padding:7px 13px;
    border-radius:8px; cursor:pointer; font-size:12px; font-weight:600; }
.ctrl-btn:hover { background:#2980b9; }
.ctrl-btn.active { background:#2980b9; }
#live-badge { position:absolute; top:12px; left:50%; transform:translateX(-50%);
    background:rgba(231,76,60,0.92); color:white; padding:5px 16px; border-radius:20px;
    font-size:11px; font-weight:700; z-index:10; animation:pulse 1.5s infinite; }
@keyframes pulse { 0%,100% {opacity:1;} 50% {opacity:0.55;} }
.leaflet-popup-content-wrapper { background:rgba(15,25,35,0.96) !important; border:1px solid #ffffff33 !important;
    border-radius:8px !important; color:white !important; }
.leaflet-popup-content { margin:10px 14px !important; font-size:12px !important; }
.leaflet-popup-tip { background:rgba(15,25,35,0.96) !important; }
.popup-title { font-weight:700; font-size:13px; margin-bottom:4px; }
.popup-sub { color:#aaa; font-size:11px; }
.vehicle-label { background:transparent !important; border:none !important; box-shadow:none !important;
    color:#ffd060 !important; font-weight:700; font-size:11px; text-shadow:0 0 3px #0f1923, 0 0 3px #0f1923; }
.vehicle-label::before { display:none !important; }
.stop-tooltip { font-size:11px; }
</style>
</head>
<body>
<div id="map"></div>
<div id="live-badge">&#9679; LIVE &#8212; __N_VEHICLES__ VEHICLES</div>
<div id="controls">
    <button class="ctrl-btn active" id="btn-dark" onclick="setStyle('dark')">Dark</button>
    <button class="ctrl-btn" id="btn-light" onclick="setStyle('light')">Light</button>
    <button class="ctrl-btn" id="btn-satellite" onclick="setStyle('satellite')">Satellite</button>
</div>
<script>
// Free, unlimited, no-API-key raster tiles — CARTO basemaps + Esri World Imagery
// (satellite). Leaflet (not MapLibre/Mapbox): see build_html()'s docstring in
// simulation.py for why — MapLibre's worker never completes inside Streamlit's
// component iframe, Leaflet has no such dependency.
const TILE_URLS = {
    dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    light: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
};
const TILE_ATTR = {
    dark: '&copy; OpenStreetMap contributors &copy; CARTO',
    light: '&copy; OpenStreetMap contributors &copy; CARTO',
    satellite: 'Esri, Maxar, Earthstar Geographics',
};

const ROUTE_GEOJSON = __ROUTE_JSON__;
const STOPS_GEOJSON = __STOPS_JSON__;
const VEHICLES_GEOJSON = __VEHICLES_JSON__;
const ZONE_GEOJSON = __ZONE_JSON__;
const BOUNDS = __BOUNDS_JSON__;  // [[minLon,minLat],[maxLon,maxLat]] or null — GeoJSON order

// A provisional center/zoom at construction time gives Leaflet a valid view to
// project from immediately — calling fitBounds() beforehand (on a map with no
// view yet, no tile layer yet) is what silently zoomed to max in testing.
const map = L.map('map', { zoomControl: false, center: [44.85, -0.58], zoom: 11 });
L.control.zoom({ position: 'bottomright' }).addTo(map);

let currentTileLayer = null;
function setStyle(name) {
    if (currentTileLayer) map.removeLayer(currentTileLayer);
    currentTileLayer = L.tileLayer(TILE_URLS[name], { attribution: TILE_ATTR[name], subdomains: 'abcd', maxZoom: 19 }).addTo(map);
    ['btn-dark', 'btn-light', 'btn-satellite'].forEach(id => document.getElementById(id).classList.remove('active'));
    document.getElementById('btn-' + name).classList.add('active');
}
setStyle('dark');

map.whenReady(function () {
    map.invalidateSize();
    if (BOUNDS) {
        map.fitBounds([[BOUNDS[0][1], BOUNDS[0][0]], [BOUNDS[1][1], BOUNDS[1][0]]], { padding: [40, 40] });
    } else {
        map.setView([__CENTER_LAT__, __CENTER_LON__], __ZOOM__);
    }
});

if (ZONE_GEOJSON) {
    L.geoJSON(ZONE_GEOJSON, {
        style: { color: '#5dade2', weight: 2, dashArray: '6,4', fillColor: '#2980b9', fillOpacity: 0.08 },
    }).addTo(map);
}

// Route glow (wide, translucent) underneath the solid line — same two-pass trick as before.
L.geoJSON(ROUTE_GEOJSON, { style: f => ({ color: f.properties.color, weight: 12, opacity: 0.15 }) }).addTo(map);
L.geoJSON(ROUTE_GEOJSON, { style: f => ({ color: f.properties.color, weight: 4, opacity: 0.92 }) }).addTo(map);

L.geoJSON(STOPS_GEOJSON, {
    pointToLayer: (feature, latlng) => {
        const p = feature.properties;
        return L.circleMarker(latlng, {
            radius: p.interchange ? 9 : 5,
            color: p.interchange ? '#1a1a1a' : '#ffffff',
            weight: 2,
            fillColor: p.interchange ? '#ffffff' : '#1abc9c',
            fillOpacity: 0.95,
        });
    },
    onEachFeature: (feature, layer) => {
        const p = feature.properties;
        layer.bindPopup('<div class="popup-title">' + p.name + '</div><div class="popup-sub">Line(s): ' + p.lines + '</div>');
        layer.bindTooltip(p.name, { direction: 'top', className: 'stop-tooltip' });
    },
}).addTo(map);

L.geoJSON(VEHICLES_GEOJSON, {
    pointToLayer: (feature, latlng) => {
        const p = feature.properties;
        const marker = L.circleMarker(latlng, { radius: 9, color: '#ffffff', weight: 2.5, fillColor: p.color, fillOpacity: 1 });
        marker.bindTooltip(p.label, { permanent: true, direction: 'top', offset: [0, -8], className: 'vehicle-label' });
        marker.bindPopup(
            '<div class="popup-title" style="color:' + p.color + '">' + p.label + '</div>' +
            '<div class="popup-sub">Speed: ' + p.speed + ' km/h</div>' +
            '<div class="popup-sub">Status: ' + p.status + '</div>' +
            '<div class="popup-sub">Direction: ' + p.direction + '</div>' +
            '<div class="popup-sub">GPS offset from track: ' + p.offset + ' m</div>'
        );
        return marker;
    },
}).addTo(map);
</script>
</body>
</html>"""

    html = template.replace("__ROUTE_JSON__", route_json)
    html = html.replace("__STOPS_JSON__", stops_json)
    html = html.replace("__VEHICLES_JSON__", vehicles_json)
    html = html.replace("__ZONE_JSON__", zone_json)
    html = html.replace("__BOUNDS_JSON__", bounds_json)
    html = html.replace("__N_VEHICLES__", str(n_vehicles))
    html = html.replace("__CENTER_LON__", str(center[0]))
    html = html.replace("__CENTER_LAT__", str(center[1]))
    html = html.replace("__ZOOM__", str(zoom))
    return html


def render():
    st.markdown(
        """<div style="background:linear-gradient(135deg,#1a1a2e,#2980b9);
            border-radius:12px;padding:20px 28px;margin-bottom:16px;color:white;">
            <div style="font-size:22px;font-weight:bold;">
                Live Map &#8212; Bordeaux Transit Network (real GPS + map-matching)
            </div>
            <div style="font-size:12px;opacity:0.9;margin-top:5px;">
                Real routes (GTFS shapes) &#183; Real stops (GTFS stops) &#183;
                Real vehicle GPS (GTFS-RT) snapped onto each line's track
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    lines_data, tram_keys, bus_keys, _zone_lines = load_lines_data()

    col_tram, col_bus = st.columns(2)
    with col_tram:
        show_tram = st.checkbox("🚋 Tram", value=True, key="sim_show_tram")
        tram_codes = [lines_data[k]["code"] for k in tram_keys]
        tram_selected_codes = st.multiselect(
            "Tram lines", options=tram_codes, default=tram_codes,
            key="sim_tram_lines", disabled=not show_tram, format_func=lambda c: f"Line {c}",
        ) if show_tram else []
    with col_bus:
        show_bus = st.checkbox(f"🚌 Bus ({len(bus_keys)} lines serving configured zones)", value=True, key="sim_show_bus")
        bus_codes = [lines_data[k]["code"] for k in bus_keys]
        bus_selected_codes = st.multiselect(
            "Bus lines", options=bus_codes, default=bus_codes,
            key="sim_bus_lines", disabled=not show_bus,
        ) if show_bus else []

    selected = [f"tram:{c}" for c in tram_selected_codes] + [f"bus:{c}" for c in bus_selected_codes]
    if not selected:
        st.warning("Select at least one line to display the map.")
        return

    route_to_key = {lines_data[k]["route_id"]: k for k in selected}
    raw_vehicles, error = fetch_raw_vehicles(tuple(route_to_key.keys()))

    if error:
        st.error(f"Could not fetch live data: {error}")
        st.info("Make sure `gtfs-realtime-bindings` is installed: `pip install gtfs-realtime-bindings`")
        return

    raw_vehicles = raw_vehicles or []
    vehicles = build_matched_vehicles(raw_vehicles, lines_data, route_to_key)

    route_geojson = build_route_geojson(selected, lines_data)
    stops_geojson = build_stops_geojson(selected, lines_data)
    vehicles_geojson = build_vehicles_geojson(vehicles)

    html = build_html(route_geojson, stops_geojson, vehicles_geojson, len(vehicles))
    components.html(html, height=660, scrolling=False)

    st.divider()

    # ── Overall stats ──
    total_stops = len(stops_geojson["features"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lines shown", len(selected))
    c2.metric("Active vehicles", len(vehicles))
    c3.metric("Unique stops", total_stops)
    interchanges = sum(1 for f in stops_geojson["features"] if f["properties"]["interchange"])
    c4.metric("Interchange stops", interchanges)

    # ── Per-line breakdown ──
    st.subheader("Per-line breakdown")
    rows = []
    for key in selected:
        line = lines_data[key]
        n_vehicles_line = sum(1 for v in vehicles if v["line"] == key)
        rows.append({
            "Mode": MODE_ICON[line["mode"]] + " " + line["mode"],
            "Line": line["code"],
            "Color": line["color"],
            "Stops": len(line["stops"]),
            "Route points": len(line["outbound"]) + len(line["inbound"]),
            "Active vehicles now": n_vehicles_line,
        })
    import pandas as pd
    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Color": st.column_config.TextColumn("Color"),
        },
    )
    st.caption(
        "⚠️ Passenger counts / ridership are not part of TBM's open data — the columns above "
        "reflect network structure (stops, route length) and live vehicle presence only."
    )

    with st.expander("Live vehicle list (real GTFS-RT)"):
        if vehicles:
            vrows = [{
                "Vehicle": v["label"],
                "Mode": MODE_ICON[v["mode"]] + " " + v["mode"],
                "Line": v["code"],
                "Matched lat": round(v["matched_lat"], 5),
                "Matched lon": round(v["matched_lon"], 5),
                "Offset (m)": v["offset_m"],
                "Speed (km/h)": v["speed"],
                "Direction": v["direction"],
                "Status": v["status"],
            } for v in sorted(vehicles, key=lambda x: x["label"])]
            st.dataframe(pd.DataFrame(vrows), use_container_width=True, hide_index=True)
        else:
            st.caption("No active vehicles to list right now.")

    with st.expander("How this works"):
        st.markdown("""
**Data pipeline (all real, no simulated motion):**

1. Server polls `tbm_gtfs_rt_vehicles` (GTFS-RT) every ~25 seconds, cached with `st.cache_data(ttl=25)`
2. Filters for the `route_id`(s) of the currently selected line(s)
3. Each raw GPS fix is **map-matched** to its own line's route polyline
   (built once from GTFS `shapes.txt` via `build_transit_lines.py`, run locally)
4. Direction (outbound/inbound) is inferred from which side of the route the GPS point matches closer to
5. Result is rendered on a Leaflet map (free CARTO/Esri tiles, no API key), one color per line

Tram shows all 6 official lines (A-F). Bus only shows lines that serve at
least one stop inside a configured zone (see `zones.py`) — TBM runs ~200 bus
lines across the whole métropole, so the map stays focused instead of
showing all of them.

| Layer | Source dataset | Status |
|-------|----------------|--------|
| Route lines (tram + bus) | `tbm_gtfs_static` (shapes.txt) | Real, static |
| Stops (tram + bus) | `tbm_gtfs_static` (stops.txt) | Real, static |
| Vehicle positions | `tbm_gtfs_rt_vehicles` | Real, live, polled every 25s |
| Ridership / passenger counts | — | **Not available** in TBM open data |
        """)

    if st.button("Refresh now"):
        fetch_raw_vehicles.clear()
        st.rerun()