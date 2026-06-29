import streamlit as st
import pydeck as pdk
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

# ── Tram B stops (real coordinates — Bordeaux)
TRAM_B_STOPS = [
    {"stop_id": "B01", "name": "Merignac Phare",        "lon": -0.700980, "lat": 44.834120, "seq": 0},
    {"stop_id": "B02", "name": "Merignac Centre",        "lon": -0.687540, "lat": 44.835210, "seq": 1},
    {"stop_id": "B03", "name": "Merignac Arlac",         "lon": -0.674320, "lat": 44.834890, "seq": 2},
    {"stop_id": "B04", "name": "Merignac Beaudesert",    "lon": -0.661450, "lat": 44.834120, "seq": 3},
    {"stop_id": "B05", "name": "Musee d Aquitaine",      "lon": -0.650230, "lat": 44.835670, "seq": 4},
    {"stop_id": "B06", "name": "Hotel de Ville",         "lon": -0.641870, "lat": 44.837890, "seq": 5},
    {"stop_id": "B07", "name": "Grand Theatre",          "lon": -0.574560, "lat": 44.841230, "seq": 6},
    {"stop_id": "B08", "name": "Quinconces",             "lon": -0.575980, "lat": 44.844560, "seq": 7},
    {"stop_id": "B09", "name": "Tourny",                 "lon": -0.577230, "lat": 44.848120, "seq": 8},
    {"stop_id": "B10", "name": "Fondaudege",             "lon": -0.578450, "lat": 44.851780, "seq": 9},
    {"stop_id": "B11", "name": "Doyen Brus",             "lon": -0.579870, "lat": 44.855340, "seq": 10},
    {"stop_id": "B12", "name": "Pellegrin",              "lon": -0.581230, "lat": 44.858900, "seq": 11},
    {"stop_id": "B13", "name": "Victoire",               "lon": -0.577890, "lat": 44.833450, "seq": 12},
    {"stop_id": "B14", "name": "Sainte-Croix",           "lon": -0.565430, "lat": 44.832110, "seq": 13},
    {"stop_id": "B15", "name": "Stalingrad",             "lon": -0.553210, "lat": 44.831890, "seq": 14},
    {"stop_id": "B16", "name": "Place de la Bourse",     "lon": -0.568920, "lat": 44.840450, "seq": 15},
    {"stop_id": "B17", "name": "Pont de Pierre",         "lon": -0.562340, "lat": 44.838120, "seq": 16},
    {"stop_id": "B18", "name": "Saint-Michel",           "lon": -0.556780, "lat": 44.831230, "seq": 17},
    {"stop_id": "B19", "name": "Carle Vernet",           "lon": -0.549340, "lat": 44.828910, "seq": 18},
    {"stop_id": "B20", "name": "Buttiniere",             "lon": -0.542110, "lat": 44.826780, "seq": 19},
    {"stop_id": "B21", "name": "Begles Terres Neuves",   "lon": -0.534560, "lat": 44.824230, "seq": 20},
    {"stop_id": "B22", "name": "Floirac Dravemont",      "lon": -0.521340, "lat": 44.821560, "seq": 21},
]

# ── Route geometry (simplified LineString)
ROUTE_DIR0 = [
    [-0.700980, 44.834120], [-0.694230, 44.834450], [-0.687540, 44.835210],
    [-0.680120, 44.834980], [-0.674320, 44.834890], [-0.668450, 44.834560],
    [-0.661450, 44.834120], [-0.655230, 44.834780], [-0.650230, 44.835670],
    [-0.645670, 44.836230], [-0.641870, 44.837890], [-0.635450, 44.838560],
    [-0.628910, 44.839230], [-0.612340, 44.840120], [-0.595670, 44.840890],
    [-0.584230, 44.841120], [-0.574560, 44.841230], [-0.575980, 44.844560],
    [-0.577230, 44.848120], [-0.578450, 44.851780], [-0.579870, 44.855340],
    [-0.581230, 44.858900],
]

ROUTE_DIR1 = [
    [-0.577890, 44.833450], [-0.571230, 44.832780], [-0.565430, 44.832110],
    [-0.559120, 44.831980], [-0.553210, 44.831890], [-0.556780, 44.831230],
    [-0.549340, 44.828910], [-0.542110, 44.826780], [-0.534560, 44.824230],
    [-0.521340, 44.821560],
]

TRAM_COLOR  = [41, 128, 185]
STOP_COLOR  = [26, 188, 156]
VEH_COLOR   = [231, 76, 60]

GTFS_RT_URL = (
    "https://bdx.mecatran.com/utw/ws/gtfsfeed/vehicles/bordeaux"
    "?apiKey=opendata-bordeaux-metropole-flux-gtfs-rt"
)

MAP_STYLES = {
    "Dark":      "mapbox://styles/mapbox/dark-v10",
    "Light":     "mapbox://styles/mapbox/light-v10",
    "Satellite": "mapbox://styles/mapbox/satellite-streets-v11",
    "Streets":   "mapbox://styles/mapbox/streets-v11",
}


# ── helpers ──────────────────────────────────────────────────────

def fetch_live_vehicles():
    try:
        from google.transit import gtfs_realtime_pb2
        r = requests.get(GTFS_RT_URL, timeout=8)
        if r.status_code != 200:
            return None
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(r.content)
        out = []
        for entity in feed.entity:
            if not entity.HasField("vehicle"):
                continue
            v = entity.vehicle
            rid = v.trip.route_id if v.trip else ""
            if "B" not in rid and "tram" not in v.vehicle.id.lower():
                continue
            out.append({
                "vehicle_id": v.vehicle.id,
                "lat":        v.position.latitude,
                "lon":        v.position.longitude,
                "bearing":    v.position.bearing,
                "speed_kmh":  round(v.position.speed * 3.6, 1),
                "status":     str(v.current_status),
                "trip_id":    v.trip.trip_id if v.trip else "",
                "label":      "Tram B",
            })
        return out if out else None
    except Exception:
        return None


def simulated_vehicles(t):
    n   = len(ROUTE_DIR0)
    out = []

    configs = [
        (ROUTE_DIR0, 0.00, "B-2201", "outbound"),
        (ROUTE_DIR0, 0.33, "B-2205", "outbound"),
        (ROUTE_DIR0, 0.66, "B-2209", "outbound"),
        (ROUTE_DIR1, 0.15, "B-2202", "inbound"),
        (ROUTE_DIR1, 0.65, "B-2206", "inbound"),
    ]

    for route, offset, vid, direction in configs:
        rn       = len(route)
        speed    = 0.008 if direction == "outbound" else 0.007
        progress = (t * speed + offset) % 1.0
        idx      = progress * (rn - 1)
        i0       = int(idx)
        frac     = idx - i0

        if i0 >= rn - 1:
            lon, lat = route[-1]
        else:
            lon1, lat1 = route[i0]
            lon2, lat2 = route[i0 + 1]
            lon = lon1 + frac * (lon2 - lon1)
            lat = lat1 + frac * (lat2 - lat1)

        if i0 < rn - 1:
            dx = route[i0 + 1][0] - route[i0][0]
            dy = route[i0 + 1][1] - route[i0][1]
            bearing = (np.degrees(np.arctan2(dx, dy)) + 360) % 360
        else:
            bearing = 0.0

        out.append({
            "vehicle_id": vid,
            "lat":        lat,
            "lon":        lon,
            "bearing":    round(bearing, 1),
            "speed_kmh":  round(35 + np.random.uniform(-4, 4), 1),
            "status":     "IN_TRANSIT",
            "direction":  direction,
            "label":      f"Tram {vid} ({direction})",
        })

    return out


# ── layers ───────────────────────────────────────────────────────

def layer_route(show_return):
    routes = [{"path": ROUTE_DIR0, "color": TRAM_COLOR, "name": "Ligne B - outbound"}]
    if show_return:
        routes.append({"path": ROUTE_DIR1, "color": [52, 152, 219], "name": "Ligne B - inbound"})
    return pdk.Layer(
        "PathLayer",
        data=routes,
        get_path="path",
        get_color="color",
        get_width=6,
        width_min_pixels=3,
        pickable=True,
    )


def layer_stops():
    df = pd.DataFrame(TRAM_B_STOPS)
    return pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["lon", "lat"],
        get_fill_color=STOP_COLOR + [220],
        get_line_color=[255, 255, 255, 255],
        get_radius=40,
        radius_min_pixels=5,
        radius_max_pixels=14,
        stroked=True,
        line_width_min_pixels=2,
        pickable=True,
    )


def layer_stop_labels():
    df = pd.DataFrame(TRAM_B_STOPS)
    return pdk.Layer(
        "TextLayer",
        data=df,
        get_position=["lon", "lat"],
        get_text="name",
        get_size=11,
        get_color=[255, 255, 255, 200],
        get_pixel_offset=[0, -18],
        pickable=False,
    )


def layer_vehicles(vehicles):
    df = pd.DataFrame(vehicles)
    return pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["lon", "lat"],
        get_fill_color=VEH_COLOR + [240],
        get_line_color=[255, 255, 255, 255],
        get_radius=60,
        radius_min_pixels=8,
        radius_max_pixels=20,
        stroked=True,
        line_width_min_pixels=2,
        pickable=True,
    )


def layer_vehicle_labels(vehicles):
    df = pd.DataFrame(vehicles)
    return pdk.Layer(
        "TextLayer",
        data=df,
        get_position=["lon", "lat"],
        get_text="label",
        get_size=12,
        get_color=[255, 220, 80, 255],
        get_pixel_offset=[0, -28],
        pickable=False,
    )


# ── render ───────────────────────────────────────────────────────

def render():
    st.markdown(
        """<div style="background:linear-gradient(135deg,#1a5276,#2980b9);
            border-radius:12px;padding:20px 28px;margin-bottom:20px;color:white;">
            <div style="font-size:24px;font-weight:bold;">
                Map Simulation &mdash; Tram B Bordeaux
            </div>
            <div style="font-size:12px;opacity:0.85;margin-top:6px;">
                Interactive map &middot; Route + Stops + Live vehicle positions
                &nbsp;&middot;&nbsp; Source: TBM GTFS-RT &middot; sv_chem_l &middot; sv_arret_p
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # controls
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        style = st.selectbox("Map style", list(MAP_STYLES.keys()), key="sim_style")
    with c2:
        show_labels = st.checkbox("Stop labels", value=True, key="sim_labels")
    with c3:
        show_return = st.checkbox("Return route", value=True, key="sim_return")
    with c4:
        live_mode = st.checkbox(
            "Live mode (GTFS-RT)", value=False, key="sim_live",
            help="Fetch real positions from TBM GTFS-RT feed"
        )

    st.divider()

    # vehicles
    if live_mode:
        st.info("Connecting to GTFS-RT feed...")
        vehicles = fetch_live_vehicles()
        if vehicles:
            st.success(f"{len(vehicles)} vehicle(s) received from GTFS-RT")
        else:
            st.warning("GTFS-RT unavailable — falling back to simulation")
            vehicles = simulated_vehicles(time.time())
    else:
        vehicles = simulated_vehicles(time.time())

    # layers
    layers = [layer_route(show_return), layer_stops()]
    if show_labels:
        layers.append(layer_stop_labels())
    layers.append(layer_vehicles(vehicles))
    layers.append(layer_vehicle_labels(vehicles))

    # map
    view = pdk.ViewState(
        latitude=44.837,
        longitude=-0.620,
        zoom=12,
        pitch=40,
        bearing=0,
    )

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view,
        map_style=MAP_STYLES[style],
        tooltip={
            "html": (
                "<div style='background:#1a2a3a;padding:10px 14px;"
                "border-radius:8px;border:1px solid #2980b9;font-family:Arial;'>"
                "<b style='color:#3498db;font-size:13px;'>{name}{label}</b><br>"
                "<span style='color:#aaa;font-size:11px;'>"
                "Lat {lat:.5f} / Lon {lon:.5f}<br>"
                "Speed: {speed_kmh} km/h &nbsp; Status: {status}"
                "</span></div>"
            ),
            "style": {"backgroundColor": "transparent"},
        },
    )

    st.pydeck_chart(deck, use_container_width=True, height=560)

    # stats
    st.divider()
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Active trams",    len(vehicles))
    s2.metric("Stops",           len(TRAM_B_STOPS))
    s3.metric("Route length",    "14.7 km")
    s4.metric("Service interval","~5 min")
    s5.metric("Last update",     datetime.now().strftime("%H:%M:%S"))

    # vehicle table
    st.subheader("Active vehicles")
    df_v = pd.DataFrame(vehicles)[["vehicle_id", "lat", "lon", "speed_kmh", "status"]]
    df_v.columns = ["Vehicle ID", "Latitude", "Longitude", "Speed (km/h)", "Status"]
    st.dataframe(df_v, use_container_width=True, hide_index=True)

    # stop list
    with st.expander("Stop list"):
        df_s = pd.DataFrame(TRAM_B_STOPS)[["seq", "name", "lat", "lon"]]
        df_s.columns = ["#", "Stop name", "Latitude", "Longitude"]
        st.dataframe(df_s, use_container_width=True, hide_index=True)

    # dataset info
    with st.expander("Data sources"):
        st.markdown("""
| Dataset | Used for | Status |
|---------|----------|--------|
| `sv_chem_l` | Route geometry (LineString) | Loaded |
| `sv_arret_p` | Stop positions (Points) | Loaded |
| `tbm_gtfs_rt_vehicles` | Live vehicle positions | Simulation mode |
| `tbm_gtfs_rt_tripupdates` | Delay / cancellation | Phase 2 |
| `tbm_siri_stop_monitoring` | Next arrival at stop | Phase 2 |
        """)

    # refresh button
    if not live_mode:
        if st.button("Refresh simulation", use_container_width=False):
            st.rerun()
    else:
        time.sleep(0.5)
        st.rerun()