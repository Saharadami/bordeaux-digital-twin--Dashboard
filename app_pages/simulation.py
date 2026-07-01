import streamlit as st
import streamlit.components.v1 as components
import requests
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from map_matching import match_vehicle

MAPBOX_TOKEN = st.secrets.get("MAPBOX_TOKEN", os.environ.get("MAPBOX_TOKEN", ""))

GTFS_RT_URL = (
    "https://bdx.mecatran.com/utw/ws/gtfsfeed/vehicles/bordeaux"
    "?apiKey=opendata-bordeaux-metropole-flux-gtfs-rt"
)
STATUS_MAP = {0: "INCOMING_AT", 1: "STOPPED_AT", 2: "IN_TRANSIT_TO"}

# Fallback colors, only used if a line's GTFS route_color was empty
FALLBACK_COLORS = {
    "A": "#831F82", "B": "#E50040", "C": "#D35098",
    "D": "#9262A3", "E": "#967651", "F": "#F08700",
}

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "sim_assets", "tram_all_lines.json")


@st.cache_data(show_spinner=False)
def load_lines_data():
    """Returns {"A": {route_id, color, outbound, inbound, stops}, "B": {...}, ...}"""
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    for letter, line in data.items():
        if not line.get("color"):
            line["color"] = FALLBACK_COLORS.get(letter, "#e74c3c")
    return data


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


def build_matched_vehicles(raw_vehicles, lines_data, route_to_letter):
    """Run map-matching per vehicle, using its own line's route geometry."""
    out = []
    for rv in raw_vehicles:
        letter = route_to_letter.get(rv["route_id"])
        line = lines_data.get(letter)
        if not line:
            continue
        m = match_vehicle(rv["lon"], rv["lat"], line["outbound"], line["inbound"])
        if m is None:
            continue
        out.append({
            "label":       f"{letter} · " + rv["id"].split(":")[-1],
            "line":        letter,
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


def build_stops_geojson(selected_letters, lines_data):
    """Dedupe stops across selected lines; stops served by 2+ lines are marked as interchanges."""
    stop_lines = {}   # stop_id -> {"name":..., "lat":..., "lon":..., "lines": set()}
    for letter in selected_letters:
        for s in lines_data[letter]["stops"]:
            entry = stop_lines.setdefault(s["id"], {"name": s["name"], "lat": s["lat"], "lon": s["lon"], "lines": set()})
            entry["lines"].add(letter)

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


def build_route_geojson(selected_letters, lines_data):
    features = []
    for letter in selected_letters:
        line = lines_data[letter]
        for dir_name, coords in [("outbound", line["outbound"]), ("inbound", line["inbound"])]:
            if coords:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {"line": letter, "dir": dir_name, "color": line["color"]},
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


def build_html(route_geojson, stops_geojson, vehicles_geojson, n_vehicles):
    route_json = json.dumps(route_geojson)
    stops_json = json.dumps(stops_geojson)
    vehicles_json = json.dumps(vehicles_geojson)

    template = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<link href="https://api.mapbox.com/mapbox-gl-js/v3.3.0/mapbox-gl.css" rel="stylesheet"/>
<script src="https://api.mapbox.com/mapbox-gl-js/v3.3.0/mapbox-gl.js"></script>
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
.mapboxgl-popup-content { background:rgba(15,25,35,0.96) !important; border:1px solid #ffffff33 !important;
    border-radius:8px !important; color:white !important; padding:10px 14px !important; font-size:12px !important; }
.popup-title { font-weight:700; font-size:13px; margin-bottom:4px; }
.popup-sub { color:#aaa; font-size:11px; }
</style>
</head>
<body>
<div id="map"></div>
<div id="live-badge">&#9679; LIVE &#8212; __N_VEHICLES__ TRAMS</div>
<div id="controls">
    <button class="ctrl-btn active" id="btn-dark" onclick="setStyle('dark')">Dark</button>
    <button class="ctrl-btn" id="btn-light" onclick="setStyle('light')">Light</button>
    <button class="ctrl-btn" id="btn-satellite" onclick="setStyle('satellite')">Satellite</button>
    <button class="ctrl-btn active" id="btn-3d" onclick="toggle3D()">3D Buildings</button>
</div>
<script>
mapboxgl.accessToken = '__TOKEN__';
const ROUTE_GEOJSON = __ROUTE_JSON__;
const STOPS_GEOJSON = __STOPS_JSON__;
const VEHICLES_GEOJSON = __VEHICLES_JSON__;

const map = new mapboxgl.Map({
    container: 'map',
    style: 'mapbox://styles/mapbox/dark-v11',
    center: [-0.58, 44.85],
    zoom: 11.3,
    pitch: 45,
    bearing: -10,
});
map.addControl(new mapboxgl.NavigationControl(), 'bottom-right');

let show3D = true;

function setStyle(name) {
    const styles = {dark:'mapbox://styles/mapbox/dark-v11', light:'mapbox://styles/mapbox/light-v11',
        satellite:'mapbox://styles/mapbox/satellite-streets-v12'};
    map.setStyle(styles[name]);
    ['btn-dark','btn-light','btn-satellite'].forEach(id => document.getElementById(id).classList.remove('active'));
    document.getElementById('btn-'+name).classList.add('active');
    map.once('style.load', addLayers);
}

function toggle3D() {
    show3D = !show3D;
    document.getElementById('btn-3d').classList.toggle('active', show3D);
    if (map.getLayer('3d-buildings')) map.setLayoutProperty('3d-buildings','visibility', show3D?'visible':'none');
}

function addLayers() {
    if (!map.getSource('route')) map.addSource('route', {type:'geojson', data:ROUTE_GEOJSON});
    if (!map.getLayer('route-glow')) map.addLayer({
        id:'route-glow', type:'line', source:'route',
        layout:{'line-join':'round','line-cap':'round'},
        paint:{'line-color':['get','color'],'line-width':14,'line-opacity':0.14,'line-blur':6}
    });
    if (!map.getLayer('route-line')) map.addLayer({
        id:'route-line', type:'line', source:'route',
        layout:{'line-join':'round','line-cap':'round'},
        paint:{'line-color':['get','color'],'line-width':4.5,'line-opacity':0.92}
    });

    if (!map.getSource('stops')) map.addSource('stops', {type:'geojson', data:STOPS_GEOJSON});
    if (!map.getLayer('stops-circle')) map.addLayer({
        id:'stops-circle', type:'circle', source:'stops',
        paint:{
            'circle-radius':['case',['get','interchange'],
                ['interpolate',['linear'],['zoom'],10,6,13,10,16,16],
                ['interpolate',['linear'],['zoom'],10,3.5,13,6,16,11]],
            'circle-color':['case',['get','interchange'],'#ffffff','#1abc9c'],
            'circle-stroke-color':['case',['get','interchange'],'#1a1a1a','#ffffff'],
            'circle-stroke-width':2, 'circle-opacity':0.95
        }
    });
    if (!map.getLayer('stops-label')) map.addLayer({
        id:'stops-label', type:'symbol', source:'stops', minzoom:13,
        layout:{'text-field':['get','name'],'text-font':['Open Sans Semibold','Arial Unicode MS Bold'],
            'text-size':10.5,'text-offset':[0,-1.6],'text-anchor':'bottom'},
        paint:{'text-color':'#ffffff','text-halo-color':'#0f1923','text-halo-width':1.5}
    });

    if (!map.getSource('vehicles')) map.addSource('vehicles', {type:'geojson', data:VEHICLES_GEOJSON});
    if (!map.getLayer('vehicles-glow')) map.addLayer({
        id:'vehicles-glow', type:'circle', source:'vehicles',
        paint:{'circle-radius':['interpolate',['linear'],['zoom'],10,14,14,24,16,32],
            'circle-color':['get','color'],'circle-opacity':0.22,'circle-blur':1}
    });
    if (!map.getLayer('vehicles-circle')) map.addLayer({
        id:'vehicles-circle', type:'circle', source:'vehicles',
        paint:{'circle-radius':['interpolate',['linear'],['zoom'],10,7,13,13,16,18],
            'circle-color':['get','color'],'circle-stroke-color':'#ffffff','circle-stroke-width':2.5}
    });
    if (!map.getLayer('vehicles-label')) map.addLayer({
        id:'vehicles-label', type:'symbol', source:'vehicles', minzoom:11,
        layout:{'text-field':['get','label'],'text-font':['Open Sans Bold','Arial Unicode MS Bold'],
            'text-size':11,'text-offset':[0,-2.2],'text-anchor':'bottom'},
        paint:{'text-color':'#ffd060','text-halo-color':'#0f1923','text-halo-width':1.5}
    });

    if (!map.getLayer('3d-buildings')) map.addLayer({
        id:'3d-buildings', source:'composite', 'source-layer':'building',
        filter:['==','extrude','true'], type:'fill-extrusion', minzoom:13,
        paint:{'fill-extrusion-color':'#1a2a3a','fill-extrusion-height':['get','height'],
            'fill-extrusion-base':['get','min_height'],'fill-extrusion-opacity':0.7}
    });

    map.on('click','stops-circle', e => {
        const p=e.features[0].properties, c=e.features[0].geometry.coordinates;
        new mapboxgl.Popup({offset:12}).setLngLat(c)
            .setHTML('<div class="popup-title">'+p.name+'</div><div class="popup-sub">Line(s): '+p.lines+'</div>')
            .addTo(map);
    });
    map.on('click','vehicles-circle', e => {
        const p=e.features[0].properties, c=e.features[0].geometry.coordinates;
        new mapboxgl.Popup({offset:12}).setLngLat(c)
            .setHTML('<div class="popup-title" style="color:'+p.color+'">'+p.label+'</div>'+
                '<div class="popup-sub">Speed: '+p.speed+' km/h</div>'+
                '<div class="popup-sub">Status: '+p.status+'</div>'+
                '<div class="popup-sub">Direction: '+p.direction+'</div>'+
                '<div class="popup-sub">GPS offset from track: '+p.offset+' m</div>')
            .addTo(map);
    });
    map.on('mouseenter','stops-circle', () => map.getCanvas().style.cursor='pointer');
    map.on('mouseleave','stops-circle', () => map.getCanvas().style.cursor='');
    map.on('mouseenter','vehicles-circle', () => map.getCanvas().style.cursor='pointer');
    map.on('mouseleave','vehicles-circle', () => map.getCanvas().style.cursor='');
}

map.on('load', addLayers);
</script>
</body>
</html>"""

    html = template.replace("__TOKEN__", MAPBOX_TOKEN)
    html = html.replace("__ROUTE_JSON__", route_json)
    html = html.replace("__STOPS_JSON__", stops_json)
    html = html.replace("__VEHICLES_JSON__", vehicles_json)
    html = html.replace("__N_VEHICLES__", str(n_vehicles))
    return html


def render():
    st.markdown(
        """<div style="background:linear-gradient(135deg,#1a1a2e,#2980b9);
            border-radius:12px;padding:20px 28px;margin-bottom:16px;color:white;">
            <div style="font-size:22px;font-weight:bold;">
                Live Map &#8212; Bordeaux Tram Network (real GPS + map-matching)
            </div>
            <div style="font-size:12px;opacity:0.9;margin-top:5px;">
                Real routes (GTFS shapes) &#183; Real stops (GTFS stops) &#183;
                Real vehicle GPS (GTFS-RT) snapped onto each line's track
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    lines_data = load_lines_data()
    all_letters = list(lines_data.keys())  # ["A","B","C","D","E","F"]

    selected = st.multiselect(
        "Tram lines to show",
        options=all_letters,
        default=all_letters,
        key="sim_selected_lines",
        format_func=lambda l: f"Line {l}",
    )
    if not selected:
        st.warning("Select at least one line to display the map.")
        return

    route_to_letter = {lines_data[l]["route_id"]: l for l in selected}
    raw_vehicles, error = fetch_raw_vehicles(tuple(route_to_letter.keys()))

    if error:
        st.error(f"Could not fetch live data: {error}")
        st.info("Make sure `gtfs-realtime-bindings` is installed: `pip install gtfs-realtime-bindings`")
        return

    raw_vehicles = raw_vehicles or []
    vehicles = build_matched_vehicles(raw_vehicles, lines_data, route_to_letter)

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
    c2.metric("Active trams", len(vehicles))
    c3.metric("Unique stops", total_stops)
    interchanges = sum(1 for f in stops_geojson["features"] if f["properties"]["interchange"])
    c4.metric("Interchange stops", interchanges)

    # ── Per-line breakdown ──
    st.subheader("Per-line breakdown")
    rows = []
    for letter in selected:
        line = lines_data[letter]
        n_vehicles_line = sum(1 for v in vehicles if v["line"] == letter)
        rows.append({
            "Line": letter,
            "Color": line["color"],
            "Stops": len(line["stops"]),
            "Route points": len(line["outbound"]) + len(line["inbound"]),
            "Active trams now": n_vehicles_line,
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
                "Line": v["line"],
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
   (built once from GTFS `shapes.txt` via `build_tram_lines.py`, run locally)
4. Direction (outbound/inbound) is inferred from which side of the route the GPS point matches closer to
5. Result is rendered on a Mapbox GL map, one color per line (official TBM `route_color`)

| Layer | Source dataset | Status |
|-------|----------------|--------|
| Route lines (A-F) | `tbm_gtfs_static` (shapes.txt) | Real, static |
| Stops (A-F) | `tbm_gtfs_static` (stops.txt) | Real, static |
| Vehicle positions | `tbm_gtfs_rt_vehicles` | Real, live, polled every 25s |
| Ridership / passenger counts | — | **Not available** in TBM open data |
        """)

    if st.button("Refresh now"):
        fetch_raw_vehicles.clear()
        st.rerun()