import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import math
import re

TRAM_COLOR = "#2980b9"
TRAM_DARK  = "#1a5276"

# ══════════════════════════════════════════════════════════════════
# DATA
# ══════════════════════════════════════════════════════════════════

ENTITIES = {
    "TramLine": {
        "layer": "Static", "color": "#2980b9",
        "source": "tbm_gtfs_static · sv_chem_l",
        "description": "Route definition — geometry, direction, identifiers",
        "fields": [
            ("line_id",          "VARCHAR(10)",  "PK"),
            ("route_id",         "VARCHAR(50)",  "GTFS ref"),
            ("ligne_id",         "VARCHAR(50)",  "SAEIV ref"),
            ("route_short_name", "VARCHAR(10)",  ""),
            ("route_long_name",  "VARCHAR(200)", ""),
            ("route_color",      "CHAR(6)",      "hex"),
            ("direction_0_name", "VARCHAR(100)", ""),
            ("direction_1_name", "VARCHAR(100)", ""),
            ("total_stops",      "INTEGER",      ""),
            ("length_m",         "FLOAT",        ""),
            ("geometry_0",       "GEOMETRY",     "PostGIS LineString"),
            ("geometry_1",       "GEOMETRY",     "PostGIS LineString"),
        ]
    },
    "TramStop": {
        "layer": "Static", "color": "#1abc9c",
        "source": "tbm_gtfs_static · sv_arret_p",
        "description": "Physical stop — location, name, accessibility",
        "fields": [
            ("stop_id",            "VARCHAR(50)",  "PK"),
            ("arret_id",           "VARCHAR(50)",  "SAEIV ref"),
            ("stop_name",          "VARCHAR(100)", ""),
            ("stop_sequence",      "INTEGER",      "on line B"),
            ("stop_lat",           "FLOAT",        "WGS84"),
            ("stop_lon",           "FLOAT",        "WGS84"),
            ("wheelchair_boarding","SMALLINT",     "0/1/2"),
            ("pmr_acces",          "BOOLEAN",      "from SAEIV"),
            ("geometry",           "GEOMETRY",     "PostGIS Point"),
        ]
    },
    "TramTrip": {
        "layer": "Static", "color": "#8e44ad",
        "source": "tbm_gtfs_static (trips.txt)",
        "description": "One complete service run terminus to terminus",
        "fields": [
            ("trip_id",       "VARCHAR(100)", "PK"),
            ("line_id",       "VARCHAR(10)",  "FK → TramLine"),
            ("shape_id",      "VARCHAR(100)", "for animation"),
            ("service_id",    "VARCHAR(50)",  "weekday/weekend"),
            ("trip_headsign", "VARCHAR(100)", "destination sign"),
            ("direction_id",  "SMALLINT",     "0/1"),
            ("bikes_allowed", "SMALLINT",     ""),
            ("start_time",    "TIME",         ""),
            ("end_time",      "TIME",         ""),
            ("stop_count",    "INTEGER",      ""),
        ]
    },
    "TramStopTime": {
        "layer": "Static", "color": "#e67e22",
        "source": "tbm_gtfs_static (stop_times.txt)",
        "description": "Scheduled arrival/departure per stop per trip",
        "fields": [
            ("stoptime_id",   "BIGSERIAL",    "PK"),
            ("trip_id",       "VARCHAR(100)", "FK → TramTrip"),
            ("stop_id",       "VARCHAR(50)",  "FK → TramStop"),
            ("stop_sequence", "INTEGER",      ""),
            ("arrival_time",  "TIME",         "can exceed 24:00"),
            ("departure_time","TIME",         ""),
            ("pickup_type",   "SMALLINT",     "0=regular"),
            ("drop_off_type", "SMALLINT",     "0=regular"),
        ]
    },
    "TramVehicle": {
        "layer": "TimeSeries", "color": "#c0392b",
        "source": "tbm_gtfs_rt_vehicles",
        "description": "Live GPS position every ~30s — core for MiniTokyo3D animation",
        "fields": [
            ("position_id",    "BIGSERIAL",   "PK · TimescaleDB"),
            ("vehicle_id",     "VARCHAR(50)", "e.g. ineo-tram:2201"),
            ("trip_id",        "VARCHAR(100)","FK → TramTrip"),
            ("line_id",        "VARCHAR(10)", "FK → TramLine"),
            ("timestamp",      "TIMESTAMPTZ", "TimescaleDB"),
            ("latitude",       "FLOAT",       ""),
            ("longitude",      "FLOAT",       ""),
            ("bearing",        "FLOAT",       "0-360 degrees"),
            ("speed_ms",       "FLOAT",       "m/s"),
            ("current_stop_seq","INTEGER",    ""),
            ("current_status", "VARCHAR(20)", "IN_TRANSIT/STOPPED"),
            ("stop_id",        "VARCHAR(50)", "FK → TramStop"),
            ("direction_id",   "SMALLINT",    "0/1"),
            ("geometry",       "GEOMETRY",    "PostGIS Point"),
        ]
    },
    "TramDelay": {
        "layer": "TimeSeries", "color": "#e74c3c",
        "source": "tbm_gtfs_rt_tripupdates",
        "description": "Real-time delay per stop per trip — negative = early",
        "fields": [
            ("delay_id",         "BIGSERIAL",   "PK · TimescaleDB"),
            ("trip_id",          "VARCHAR(100)","FK → TramTrip"),
            ("stop_id",          "VARCHAR(50)", "FK → TramStop"),
            ("stop_sequence",    "INTEGER",     ""),
            ("timestamp",        "TIMESTAMPTZ", "TimescaleDB"),
            ("arrival_delay_s",  "INTEGER",     "seconds"),
            ("departure_delay_s","INTEGER",     "seconds"),
            ("schedule_rel",     "VARCHAR(20)", "SCHEDULED/SKIPPED"),
            ("trip_schedule_rel","VARCHAR(20)", "SCHEDULED/CANCELED"),
        ]
    },
    "TramNextArrival": {
        "layer": "TimeSeries", "color": "#2ecc71",
        "source": "tbm_siri_stop_monitoring",
        "description": "Next arrivals at a stop — for station info panel on map",
        "fields": [
            ("arrival_id",        "BIGSERIAL",   "PK · TimescaleDB"),
            ("stop_id",           "VARCHAR(50)", "FK → TramStop"),
            ("vehicle_id",        "VARCHAR(50)", ""),
            ("trip_id",           "VARCHAR(100)","FK → TramTrip"),
            ("destination_name",  "VARCHAR(100)","headsign"),
            ("aimed_arrival",     "TIMESTAMPTZ", "planned"),
            ("expected_arrival",  "TIMESTAMPTZ", "real-time"),
            ("aimed_departure",   "TIMESTAMPTZ", "planned"),
            ("expected_departure","TIMESTAMPTZ", "real-time"),
            ("occupancy",         "VARCHAR(20)", "SEATS/STANDING/FULL"),
            ("vehicle_at_stop",   "BOOLEAN",     ""),
            ("fetched_at",        "TIMESTAMPTZ", "TimescaleDB"),
        ]
    },
    "TramAlert": {
        "layer": "TimeSeries", "color": "#f39c12",
        "source": "tbm_gtfs_rt_alerts",
        "description": "Service disruption alerts — cause, effect, active period",
        "fields": [
            ("alert_id",      "VARCHAR(100)", "PK"),
            ("cause",         "VARCHAR(50)",  "ACCIDENT/CONSTRUCTION/..."),
            ("effect",        "VARCHAR(50)",  "NO_SERVICE/DETOUR/..."),
            ("affected_route","VARCHAR(50)",  "FK → TramLine"),
            ("affected_stop", "VARCHAR(50)",  "FK → TramStop (nullable)"),
            ("affected_trip", "VARCHAR(100)", "FK → TramTrip (nullable)"),
            ("header_fr",     "TEXT",         ""),
            ("description_fr","TEXT",         ""),
            ("active_from",   "TIMESTAMPTZ",  ""),
            ("active_until",  "TIMESTAMPTZ",  "nullable"),
            ("fetched_at",    "TIMESTAMPTZ",  "TimescaleDB"),
        ]
    },
}

ERD_RELATIONS = [
    ("TramLine",  "TramTrip",        "1","N","has trips"),
    ("TramLine",  "TramVehicle",     "1","N","hosts vehicles"),
    ("TramLine",  "TramAlert",       "1","N","disrupted by"),
    ("TramLine",  "TramStop",        "N","M","contains stops"),
    ("TramTrip",  "TramStopTime",    "1","N","has stop times"),
    ("TramTrip",  "TramVehicle",     "1","N","executed by"),
    ("TramTrip",  "TramDelay",       "1","N","has delays"),
    ("TramTrip",  "TramNextArrival", "1","N","previewed in"),
    ("TramTrip",  "TramAlert",       "1","N","canceled by"),
    ("TramStop",  "TramStopTime",    "1","N","scheduled in"),
    ("TramStop",  "TramVehicle",     "1","N","current stop of"),
    ("TramStop",  "TramDelay",       "1","N","delayed at"),
    ("TramStop",  "TramNextArrival", "1","N","queried for"),
    ("TramStop",  "TramAlert",       "1","N","affected by"),
]

ONTO_RELATIONS = [
    ("TramVehicle",    "follows",          "TramLine",       "Strong",
     "Vehicle path interpolated along route geometry via shape_id → LineString"),
    ("TramVehicle",    "executes",         "TramTrip",       "Strong",
     "vehicle_id assigned to trip_id in real-time — live position linked to schedule"),
    ("TramVehicle",    "approaches",       "TramStop",       "Strong",
     "currentStopSequence tells exactly which stop tram is heading to next"),
    ("TramDelay",      "adjusts",          "TramStopTime",   "Strong",
     "arrival_delay_s added to scheduled stop_time to compute real-time ETA"),
    ("TramDelay",      "tracks",           "TramTrip",       "Strong",
     "Each delay record tied to trip_id — CANCELED trips suppressed from animation"),
    ("TramNextArrival","enriches",         "TramStop",       "Strong",
     "SIRI stop-monitoring adds real-time next arrival per stop for info panel"),
    ("TramTrip",       "runs on",          "TramLine",       "Strong",
     "Every trip belongs to a route — route_id links trip to Ligne B definition"),
    ("TramTrip",       "visits",           "TramStop",       "Strong",
     "stop_times.txt defines ordered sequence of stops each trip visits"),
    ("TramStopTime",   "scheduled at",     "TramStop",       "Strong",
     "Each stop_time references stop_id — base timetable built from this join"),
    ("TramAlert",      "disrupts",         "TramLine",       "Strong",
     "informed_entity.route_id matches Ligne B — triggers network-level alert"),
    ("TramLine",       "contains",         "TramStop",       "Strong",
     "Line includes ordered list of stops — from stop_times joined with shapes"),
    ("TramAlert",      "relocates",        "TramStop",       "Medium",
     "STOP_MOVED alerts reference affected stop — warning shown on stop marker"),
    ("TramAlert",      "cancels",          "TramTrip",       "Medium",
     "NO_SERVICE alerts reference trip_ids — suppresses vehicle from animation"),
    ("TramVehicle",    "triggers",         "TramNextArrival","Medium",
     "Vehicle position + delay used to compute expected arrival times for panel"),
    ("TramDelay",      "corrects",         "TramNextArrival","Medium",
     "arrival_delay_s merged into SIRI feed for accurate ETA display at stop"),
]


# ══════════════════════════════════════════════════════════════════
# ERD SVG
# ══════════════════════════════════════════════════════════════════

def build_erd_svg():
    BOX_W = 230
    ROW_H = 19
    HEAD_H = 34
    PAD = 8

    POS = {
        "TramLine":       (40,   60),
        "TramTrip":       (360,  60),
        "TramStop":       (40,  460),
        "TramStopTime":   (360, 460),
        "TramVehicle":    (700,  60),
        "TramDelay":      (700, 340),
        "TramNextArrival":(700, 620),
        "TramAlert":      (360, 720),
    }

    def bh(e): return HEAD_H + len(ENTITIES[e]["fields"]) * ROW_H + PAD

    def edge(f, t):
        fx, fy = POS[f]
        tx, ty = POS[t]
        fh = bh(f)
        th = bh(t)
        fcx = fx + BOX_W // 2
        tcx = tx + BOX_W // 2
        # pick sides
        if tx >= fx + BOX_W:        x1, x2 = fx + BOX_W, tx
        elif tx + BOX_W <= fx:      x1, x2 = fx, tx + BOX_W
        else:                       x1, x2 = fcx, tcx
        if ty >= fy + fh:           y1, y2 = fy + fh // 2, ty + HEAD_H // 2
        elif ty + th <= fy:         y1, y2 = fy + HEAD_H // 2, ty + th
        else:                       y1, y2 = fy + HEAD_H // 2, ty + HEAD_H // 2
        return x1, y1, x2, y2

    lines = []
    boxes = []

    for f, t, fc, tc, lbl in ERD_RELATIONS:
        if f not in POS or t not in POS:
            continue
        x1, y1, x2, y2 = edge(f, t)
        col = ENTITIES[f]["color"]
        mx, my = (x1+x2)//2, (y1+y2)//2
        lines.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="1.5" stroke-dasharray="5,3" opacity="0.55"/>')
        lines.append(f'<text x="{x1+4}" y="{y1-4}" font-size="10" fill="{col}" font-weight="bold">{fc}</text>')
        lines.append(f'<text x="{x2-4}" y="{y2-4}" font-size="10" fill="{col}" font-weight="bold" text-anchor="end">{tc}</text>')
        lines.append(f'<text x="{mx}" y="{my-4}" font-size="9" fill="#999" text-anchor="middle" font-style="italic">{lbl}</text>')

    for name, meta in ENTITIES.items():
        x, y = POS[name]
        h = bh(name)
        color = meta["color"]
        bg = "#f0f7ff" if meta["layer"] == "Static" else "#fff5f5"

        boxes.append(f'<rect x="{x+3}" y="{y+3}" width="{BOX_W}" height="{h}" rx="7" fill="#0000001a"/>')
        boxes.append(f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{h}" rx="7" fill="{bg}" stroke="{color}" stroke-width="2"/>')
        boxes.append(f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{HEAD_H}" rx="7" fill="{color}"/>')
        boxes.append(f'<rect x="{x}" y="{y+HEAD_H-7}" width="{BOX_W}" height="7" fill="{color}"/>')

        badge = "📐 Static" if meta["layer"] == "Static" else "⏱️ RT"
        boxes.append(f'<text x="{x+BOX_W-8}" y="{y+13}" font-size="8" fill="white" opacity="0.75" text-anchor="end">{badge}</text>')
        boxes.append(f'<text x="{x+10}" y="{y+23}" font-size="12" font-weight="bold" fill="white">{name}</text>')

        for i, (fname, ftype, flag) in enumerate(meta["fields"]):
            ry = y + HEAD_H + i * ROW_H + 14
            if "PK" in flag:   ic, bg2 = "🔑", "#e8f4fd"
            elif "FK" in flag: ic, bg2 = "🔗", "#fde8e8"
            else:              ic, bg2 = " ", "transparent"

            if bg2 != "transparent":
                boxes.append(f'<rect x="{x+1}" y="{ry-13}" width="{BOX_W-2}" height="{ROW_H}" fill="{bg2}"/>')

            boxes.append(f'<text x="{x+7}" y="{ry}" font-size="9" fill="#333">{ic} {fname}</text>')
            boxes.append(f'<text x="{x+BOX_W-7}" y="{ry}" font-size="8" fill="#888" text-anchor="end" font-family="monospace">{ftype}</text>')
            if i < len(meta["fields"]) - 1:
                boxes.append(f'<line x1="{x+6}" y1="{ry+5}" x2="{x+BOX_W-6}" y2="{ry+5}" stroke="#e5e5e5" stroke-width="0.5"/>')

        src = meta["source"]
        boxes.append(f'<text x="{x+BOX_W//2}" y="{y+h+13}" font-size="8" fill="#bbb" text-anchor="middle">{src}</text>')

    legend = '''<rect x="16" y="16" width="250" height="105" rx="8" fill="white" stroke="#ddd"/>
    <text x="28" y="38" font-size="11" font-weight="bold" fill="#333">ERD — Tram B Physical Model</text>
    <rect x="28" y="50" width="11" height="11" rx="2" fill="#f0f7ff" stroke="#2980b9"/>
    <text x="46" y="60" font-size="10" fill="#555">📐 Static Reference entity</text>
    <rect x="28" y="68" width="11" height="11" rx="2" fill="#fff5f5" stroke="#c0392b"/>
    <text x="46" y="78" font-size="10" fill="#555">⏱️ Time-Series entity</text>
    <text x="28" y="96" font-size="9" fill="#888">🔑 Primary Key   🔗 Foreign Key</text>
    <text x="28" y="110" font-size="9" fill="#aaa">1/N = cardinality · dashed = FK relationship</text>'''

    return f'''<svg width="980" height="1000" xmlns="http://www.w3.org/2000/svg"
        style="background:#f8f9fa;border-radius:12px;font-family:Segoe UI,Arial,sans-serif;">
        {''.join(lines)}{''.join(boxes)}{legend}
    </svg>'''


# ══════════════════════════════════════════════════════════════════
# KNOWLEDGE GRAPH SVG
# ══════════════════════════════════════════════════════════════════

def build_ontology_svg():
    POS = {
        "TramLine":        (490,  90),
        "TramStop":        (130, 380),
        "TramTrip":        (850, 380),
        "TramStopTime":    (490, 380),
        "TramVehicle":     (130, 660),
        "TramDelay":       (490, 660),
        "TramNextArrival": (850, 660),
        "TramAlert":       (490, 940),
    }
    R = 54
    COLORS = {e: ENTITIES[e]["color"] for e in ENTITIES}
    SCOL = {"Strong": None, "Medium": "#aaaaaa"}  # Strong uses source color

    markers = ""
    for name in POS:
        col = COLORS.get(name, "#888")
        markers += (f'<marker id="a{name}" markerWidth="7" markerHeight="7" '
                    f'refX="6" refY="3" orient="auto">'
                    f'<path d="M0,0 L0,6 L7,3 z" fill="{col}" opacity="0.75"/></marker>')

    lines = []
    for f, rel, t, strength, expl in ONTO_RELATIONS:
        if f not in POS or t not in POS:
            continue
        x1, y1 = POS[f]
        x2, y2 = POS[t]
        dx, dy = x2-x1, y2-y1
        dist = max(math.sqrt(dx*dx+dy*dy), 1)
        sx = x1 + dx/dist*R
        sy = y1 + dy/dist*R
        ex = x2 - dx/dist*R
        ey = y2 - dy/dist*R
        # curve
        perp_x = -dy/dist*22
        perp_y =  dx/dist*22
        cx2 = (sx+ex)/2 + perp_x
        cy2 = (sy+ey)/2 + perp_y

        col = COLORS.get(f, "#888") if strength == "Strong" else "#aaa"
        dash = "" if strength == "Strong" else 'stroke-dasharray="7,4"'
        w = 2.2 if strength == "Strong" else 1.4

        lines.append(
            f'<path d="M{sx:.0f},{sy:.0f} Q{cx2:.0f},{cy2:.0f} {ex:.0f},{ey:.0f}" '
            f'fill="none" stroke="{col}" stroke-width="{w}" opacity="0.6" {dash} '
            f'marker-end="url(#a{f})"/>'
        )
        lines.append(
            f'<text x="{cx2:.0f}" y="{cy2:.0f}" font-size="9" fill="{col}" '
            f'opacity="0.95" text-anchor="middle" font-style="italic">{rel}</text>'
        )

    nodes = []
    for name, (cx, cy) in POS.items():
        color = COLORS[name]
        layer = ENTITIES[name]["layer"]
        icon = "📐" if layer == "Static" else "⏱️"
        nf = len(ENTITIES[name]["fields"])

        nodes.append(f'<circle cx="{cx}" cy="{cy}" r="{R+10}" fill="{color}" opacity="0.10"/>')
        nodes.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="white" stroke="{color}" stroke-width="2.5"/>')
        nodes.append(f'<text x="{cx}" y="{cy-14}" font-size="20" text-anchor="middle">{icon}</text>')

        # split name
        parts = re.findall('[A-Z][a-z]*', name)
        if len(parts) >= 2:
            l1 = parts[0]
            l2 = "".join(parts[1:])
            nodes.append(f'<text x="{cx}" y="{cy+6}" font-size="10" font-weight="bold" fill="{color}" text-anchor="middle">{l1}</text>')
            nodes.append(f'<text x="{cx}" y="{cy+19}" font-size="10" font-weight="bold" fill="{color}" text-anchor="middle">{l2}</text>')
        else:
            nodes.append(f'<text x="{cx}" y="{cy+10}" font-size="10" font-weight="bold" fill="{color}" text-anchor="middle">{name}</text>')

        # field count badge
        nodes.append(f'<rect x="{cx+35}" y="{cy-66}" width="26" height="15" rx="7" fill="{color}"/>')
        nodes.append(f'<text x="{cx+48}" y="{cy-56}" font-size="8" fill="white" text-anchor="middle" font-weight="bold">{nf}f</text>')

        # datatype props
        px = cx - 100
        py = cy + R + 10
        pw = 200
        shown_fields = ENTITIES[name]["fields"][:5]
        ph = len(shown_fields)*13 + 10

        nodes.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="4" fill="{color}12" stroke="{color}35" stroke-width="1"/>')
        for i, (fn, ft, fl) in enumerate(shown_fields):
            ic2 = "🔑" if "PK" in fl else ("🔗" if "FK" in fl else "·")
            nodes.append(f'<text x="{px+7}" y="{py+12+i*13}" font-size="8" fill="{color}" font-family="monospace">{ic2} {fn}</text>')

        extra = len(ENTITIES[name]["fields"]) - 5
        if extra > 0:
            nodes.append(f'<text x="{px+7}" y="{py+12+5*13}" font-size="8" fill="{color}" opacity="0.55">+{extra} more...</text>')

        nodes.append(f'<text x="{cx}" y="{py+ph+13}" font-size="8" fill="#bbb" text-anchor="middle">{ENTITIES[name]["source"]}</text>')

    legend = '''<rect x="16" y="16" width="265" height="130" rx="8" fill="white" stroke="#ddd"/>
    <text x="28" y="40" font-size="11" font-weight="bold" fill="#333">Ontology — Knowledge Graph</text>
    <circle cx="38" cy="60" r="8" fill="#2980b9" opacity="0.25" stroke="#2980b9" stroke-width="1.5"/>
    <text x="54" y="64" font-size="10" fill="#555">📐 Static Reference class</text>
    <circle cx="38" cy="82" r="8" fill="#c0392b" opacity="0.25" stroke="#c0392b" stroke-width="1.5"/>
    <text x="54" y="86" font-size="10" fill="#555">⏱️ Time-Series class</text>
    <line x1="25" y1="104" x2="55" y2="104" stroke="#2980b9" stroke-width="2.2"/>
    <text x="63" y="108" font-size="10" fill="#555">Strong object property (causal)</text>
    <line x1="25" y1="122" x2="55" y2="122" stroke="#aaa" stroke-width="1.4" stroke-dasharray="7,4"/>
    <text x="63" y="126" font-size="10" fill="#555">Medium object property</text>
    <text x="28" y="142" font-size="9" fill="#aaa">italic labels = relation names · f = field count</text>'''

    return f'''<svg width="1050" height="1130" xmlns="http://www.w3.org/2000/svg"
        style="background:#f8f9fa;border-radius:12px;font-family:Segoe UI,Arial,sans-serif;">
        <defs>{markers}</defs>
        {''.join(lines)}{''.join(nodes)}{legend}
    </svg>'''


# ══════════════════════════════════════════════════════════════════
# RENDER FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def render_erd():
    st.caption("Entity-Relationship Diagram — physical data model · 8 entities · 14 FK relationships · cardinality shown")
    svg = build_erd_svg()
    components.html(f'<div style="overflow:auto">{svg}</div>', height=1010)


def render_entity_table():
    layer_f  = st.selectbox("Layer", ["All","Static","TimeSeries"], key="tb_el")
    entity_f = st.selectbox("Entity", ["All"]+list(ENTITIES.keys()), key="tb_ee")

    for name, meta in ENTITIES.items():
        if layer_f  != "All" and meta["layer"] != layer_f:  continue
        if entity_f != "All" and name != entity_f:          continue

        color = meta["color"]
        badge = "📐 Static Reference" if meta["layer"]=="Static" else "⏱️ Time-Series"
        st.markdown(
            f'<div style="border-left:5px solid {color};padding:10px 16px;'
            f'background:linear-gradient(90deg,{color}09,transparent);border-radius:0 8px 8px 0;margin-bottom:6px;">'
            f'<span style="font-size:15px;font-weight:bold;color:{color};">{name}</span>'
            f'<span style="background:{color}20;color:{color};padding:2px 10px;border-radius:10px;'
            f'font-size:10px;font-weight:bold;margin-left:10px;">{badge}</span>'
            f'<span style="font-size:11px;color:#666;margin-left:10px;">{meta["description"]}</span><br>'
            f'<span style="font-size:10px;color:#aaa;">Source: {meta["source"]}</span></div>',
            unsafe_allow_html=True
        )
        rows = [{"Field": fn, "Type": ft,
                 "Role": "🔑 PK" if "PK" in fl else ("🔗 FK" if "FK" in fl else "📐" if "PostGIS" in fl else "⏱️" if "TimescaleDB" in fl else ""),
                 "Note": fl}
                for fn, ft, fl in meta["fields"]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=min(len(rows)*35+40,380))
        st.markdown("&nbsp;", unsafe_allow_html=True)


def render_ontology_graph():
    st.caption("Knowledge Graph — 8 classes · 15 object properties · Strong = causal · Medium = correlational")
    svg = build_ontology_svg()
    components.html(f'<div style="overflow:auto">{svg}</div>', height=1140)


def render_relations_table():
    st.caption(f"{len(ONTO_RELATIONS)} object properties between Tram B classes")
    sf = st.selectbox("Strength", ["All","Strong","Medium"], key="tb_os")
    ef = st.selectbox("Class",    ["All"]+list(ENTITIES.keys()), key="tb_oe")

    filtered = [(f,r,t,s,e) for f,r,t,s,e in ONTO_RELATIONS
                if (sf=="All" or s==sf) and (ef=="All" or f==ef or t==ef)]

    c1,c2,c3 = st.columns(3)
    c1.metric("Properties", len(filtered))
    c2.metric("Strong", sum(1 for _,_,_,s,_ in filtered if s=="Strong"))
    c3.metric("Medium", sum(1 for _,_,_,s,_ in filtered if s=="Medium"))
    st.divider()

    for f,rel,t,strength,expl in filtered:
        fc = ENTITIES.get(f,{}).get("color","#888")
        tc = ENTITIES.get(t,{}).get("color","#888")
        sc = fc if strength=="Strong" else "#aaa"
        st.markdown(
            f'<div style="border-left:3px solid {sc};padding:10px 16px;margin:6px 0;'
            f'background:white;border-radius:0 8px 8px 0;box-shadow:0 1px 3px #0000000d;">'
            f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'
            f'<code style="color:{fc};font-weight:bold;font-size:13px;">{f}</code>'
            f'<span style="background:#f0f4ff;color:#3949ab;padding:2px 10px;border-radius:10px;font-size:11px;font-style:italic;">— {rel} →</span>'
            f'<code style="color:{tc};font-weight:bold;font-size:13px;">{t}</code>'
            f'<span style="margin-left:auto;font-size:11px;color:{sc};font-weight:bold;">{strength}</span>'
            f'</div><div style="font-size:11px;color:#555;margin-top:6px;">{expl}</div></div>',
            unsafe_allow_html=True
        )


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def render():
    st.markdown(
        f'<div style="background:linear-gradient(135deg,{TRAM_DARK},{TRAM_COLOR});'
        f'border-radius:12px;padding:22px 28px;margin-bottom:20px;color:white;">'
        f'<div style="font-size:26px;font-weight:bold;">🚋 Tram B — Data Infrastructure</div>'
        f'<div style="font-size:12px;opacity:0.85;margin-top:6px;">'
        f'8 datasets · 8 entities · 14 FK relationships · 15 semantic object properties'
        f'&nbsp;·&nbsp; TBM GTFS · GTFS-RT · SIRI-Lite · SAEIV</div></div>',
        unsafe_allow_html=True
    )

    tab1, tab2 = st.tabs(["🔷 Data Model", "🔗 Ontology"])

    with tab1:
        s1, s2 = st.tabs(["📐 ERD Diagram", "📋 Entity Details"])
        with s1: render_erd()
        with s2: render_entity_table()

    with tab2:
        s1, s2 = st.tabs(["🌐 Knowledge Graph", "📊 Object Properties"])
        with s1: render_ontology_graph()
        with s2: render_relations_table()