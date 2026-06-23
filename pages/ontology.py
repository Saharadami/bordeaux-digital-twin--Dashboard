import streamlit as st
import streamlit.components.v1 as components
import math

DOMAIN_META = {
    "Mobility":       {"icon": "🚗", "color": "#e8593c"},
    "Weather":        {"icon": "🌤️", "color": "#3b8bd4"},
    "AirQuality":     {"icon": "🌬️", "color": "#1d9e75"},
    "Water":          {"icon": "💧", "color": "#0077b6"},
    "Energy":         {"icon": "⚡", "color": "#f4a261"},
    "Buildings":      {"icon": "🏢", "color": "#ba7517"},
    "Population":     {"icon": "👥", "color": "#9b59b6"},
    "Environment":    {"icon": "🌿", "color": "#3b6d11"},
    "Sensors":        {"icon": "📡", "color": "#e74c3c"},
    "Online DataSet": {"icon": "🌐", "color": "#c0392b"},
}

# Ontology semantic relationships
# (from, relationship, to, strength, explanation)
ONTO_RELATIONS = [
    # Strong — P1 core causal
    ("Mobility",    "generates",          "AirQuality",   "Strong",  "Vehicle emissions are the primary source of NO2 and PM10/PM2.5 in urban areas"),
    ("Mobility",    "depends on",         "Sensors",      "Strong",  "All traffic measurements originate from physical loop detectors and counters"),
    ("Mobility",    "fed by",             "Online DataSet","Strong", "Real-time traffic and bike feeds are the ingestion layer for mobility data"),
    ("Mobility",    "influenced by",      "Weather",      "Strong",  "Rain, fog, ice and heat directly alter traffic flow and modal choices"),
    ("Mobility",    "shaped by",          "Population",   "Strong",  "Population density and commuting patterns determine traffic demand"),
    ("Weather",     "drives",             "Water",        "Strong",  "Upstream precipitation controls Garonne river level with 6-48h lag"),
    ("Weather",     "controls",           "AirQuality",   "Strong",  "Wind dispersion and temperature inversions govern pollutant concentration"),
    ("Weather",     "determines",         "Energy",       "Strong",  "Temperature drives heating/cooling demand; solar radiation drives PV output"),
    ("AirQuality",  "impacts",            "Population",   "Strong",  "Long-term PM2.5 and NO2 exposure causes premature deaths and DALYs"),
    ("AirQuality",  "modulated by",       "Environment",  "Strong",  "Tree canopy absorbs PM; industrial sites emit NOx and SO2"),
    ("Water",       "interacts with",     "Environment",  "Strong",  "Flood zones, green infrastructure and hydrographic network are deeply linked"),
    ("Energy",      "determined by",      "Buildings",    "Strong",  "DPE class and floor surface determine residential heating/cooling demand"),
    ("Energy",      "driven by",          "Population",   "Strong",  "Population density is the primary driver of residential energy consumption"),
    ("Buildings",   "located in",         "Population",   "Strong",  "Every building falls within an IRIS zone — spatial link to demographics"),
    ("Sensors",     "feeds",              "AirQuality",   "Strong",  "Atmo NA monitoring stations produce all AQ time-series measurements"),
    ("Sensors",     "monitors",           "Water",        "Strong",  "Vigicrues station O972001001 produces all Garonne river level data"),
    # Medium
    ("Mobility",    "connected to",       "Online DataSet","Medium", "Online datasets are the real-time source layer for mobility entities"),
    ("Weather",     "calibrated by",      "Weather",      "Medium",  "ERA5 reanalysis calibrates AROME forecast model — internal data flow"),
    ("Energy",      "tracked by",         "Sensors",      "Medium",  "Smart meters and grid sensors monitor real-time electricity consumption"),
    ("Population",  "exposed to",         "AirQuality",   "Medium",  "Gridded AQ model combined with IRIS population gives exposure per zone"),
    ("Buildings",   "assessed by",        "Energy",       "Medium",  "Solar cadastre evaluates rooftop PV potential per building"),
    ("Environment", "absorbs",            "AirQuality",   "Medium",  "Urban tree cover reduces PM and CO2 concentrations"),
    # Weak / P3
    ("Mobility",    "affects",            "Water",        "Weak",    "Flood events close roads and force traffic rerouting"),
    ("Mobility",    "stresses",           "Environment",  "Weak",    "Vehicle emissions contribute to urban tree canopy stress"),
    ("Weather",     "threatens",          "Population",   "Weak",    "Extreme heat creates vulnerability especially for elderly populations"),
    ("Water",       "endangers",          "Buildings",    "Weak",    "Flood zones create risk of damage to building stock"),
    ("AirQuality",  "devalues",           "Buildings",    "Weak",    "Poor air quality in a zone negatively affects real estate values"),
    ("Environment", "supports",           "Population",   "Weak",    "Green space accessibility correlates with quality of life indicators"),
]

CAUSAL_CHAINS = [
    {
        "title": "Urban Traffic → Air Pollution → Public Health",
        "color": "#e8593c",
        "steps": [
            {"domain": "Sensors",     "role": "measure",   "desc": "Loop detectors count vehicles and measure speed"},
            {"domain": "Mobility",    "role": "generate",  "desc": "Traffic volume × fleet emission factors"},
            {"domain": "AirQuality",  "role": "produce",   "desc": "NO2 and PM2.5 concentrations rise near busy roads"},
            {"domain": "Population",  "role": "suffer",    "desc": "Long-term exposure → DALYs and premature deaths"},
        ]
    },
    {
        "title": "Precipitation → Flood Risk → Infrastructure",
        "color": "#0077b6",
        "steps": [
            {"domain": "Weather",     "role": "trigger",   "desc": "Upstream rainfall in Pyrénées / Massif Central"},
            {"domain": "Water",       "role": "respond",   "desc": "Garonne level rises at Bordeaux with 6-48h lag"},
            {"domain": "Environment", "role": "retain",    "desc": "Green spaces and forests absorb runoff"},
            {"domain": "Mobility",    "role": "disrupt",   "desc": "Flood zones close roads and reroute traffic"},
        ]
    },
    {
        "title": "Weather → Energy Demand & Carbon",
        "color": "#f4a261",
        "steps": [
            {"domain": "Weather",     "role": "drive",     "desc": "Temperature extremes create heating/cooling peaks"},
            {"domain": "Energy",      "role": "consume",   "desc": "Grid load spikes; solar production varies with radiation"},
            {"domain": "Buildings",   "role": "determine", "desc": "DPE class modulates actual consumption per building"},
            {"domain": "AirQuality",  "role": "receive",   "desc": "Grid carbon intensity affects urban GHG footprint"},
        ]
    },
    {
        "title": "Population Density → Urban Demand",
        "color": "#9b59b6",
        "steps": [
            {"domain": "Population",  "role": "generate",  "desc": "Dense IRIS zones produce high trip generation rates"},
            {"domain": "Mobility",    "role": "absorb",    "desc": "Road network and PT lines carry the demand"},
            {"domain": "Energy",      "role": "consume",   "desc": "Residential density drives electricity and gas use"},
            {"domain": "AirQuality",  "role": "degrade",   "desc": "High density + traffic → elevated NO2 exposure"},
        ]
    },
    {
        "title": "Buildings → Energy Performance → Emissions",
        "color": "#ba7517",
        "steps": [
            {"domain": "Buildings",   "role": "define",    "desc": "DPE class (A-G) sets the energy performance baseline"},
            {"domain": "Energy",      "role": "quantify",  "desc": "kWh consumption per m² measured at substation level"},
            {"domain": "AirQuality",  "role": "track",     "desc": "Grid carbon intensity links consumption to GHG"},
            {"domain": "Environment", "role": "record",    "desc": "Territorial emissions inventory aggregates all sectors"},
        ]
    },
    {
        "title": "Sensor Network → Real-time Digital Twin",
        "color": "#e74c3c",
        "steps": [
            {"domain": "Sensors",      "role": "observe",  "desc": "Physical sensors measure traffic, AQ, river level"},
            {"domain": "Online DataSet","role": "stream",  "desc": "Real-time APIs ingest measurements every 2-10 min"},
            {"domain": "Mobility",     "role": "reflect",  "desc": "TrafficMeasure and TravelTime updated continuously"},
            {"domain": "Water",        "role": "alert",    "desc": "Flood alert level updated from river gauge data"},
        ]
    },
]

STRENGTH_COLORS = {"Strong": "#e74c3c", "Medium": "#f39c12", "Weak": "#2ecc71"}
STRENGTH_ICONS  = {"Strong": "🔴", "Medium": "🟡", "Weak": "🟢"}


def render_chains():
    st.caption(f"{len(CAUSAL_CHAINS)} causal chains identified from domain relationships")

    for chain in CAUSAL_CHAINS:
        color = chain["color"]
        st.markdown(
            f"<div style='border-left:4px solid {color};padding:10px 16px;margin-bottom:6px;"
            f"background:linear-gradient(90deg,{color}10,transparent);border-radius:0 8px 8px 0;'>"
            f"<strong style='font-size:14px;color:{color}'>{chain['title']}</strong></div>",
            unsafe_allow_html=True
        )

        steps = chain["steps"]
        cols = st.columns(len(steps) * 2 - 1)

        for i, step in enumerate(steps):
            dm = DOMAIN_META.get(step["domain"], {"icon": "📂", "color": "#888"})
            col_idx = i * 2
            with cols[col_idx]:
                st.markdown(
                    f"<div style='background:white;border:2px solid {dm['color']};border-radius:10px;"
                    f"padding:12px 8px;text-align:center;'>"
                    f"<div style='font-size:24px'>{dm['icon']}</div>"
                    f"<div style='font-weight:bold;font-size:11px;color:{dm['color']};margin:4px 0'>{step['domain']}</div>"
                    f"<div style='font-size:10px;color:#aaa;font-style:italic'>{step['role']}</div>"
                    f"<div style='font-size:10px;color:#555;margin-top:4px'>{step['desc']}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            if i < len(steps) - 1:
                with cols[col_idx + 1]:
                    st.markdown(
                        f"<div style='text-align:center;padding-top:28px;"
                        f"font-size:22px;color:{color}'>→</div>",
                        unsafe_allow_html=True
                    )
        st.markdown("---")


def render_table():
    st.caption(f"{len(ONTO_RELATIONS)} semantic relationships · filter by domain or strength")

    col1, col2 = st.columns(2)
    with col1:
        domain_filter = st.selectbox("Filter by domain", ["All"] + sorted(DOMAIN_META.keys()), key="onto_domain")
    with col2:
        strength_filter = st.selectbox("Filter by strength", ["All", "Strong", "Medium", "Weak"], key="onto_strength")

    filtered = ONTO_RELATIONS
    if domain_filter != "All":
        filtered = [r for r in filtered if r[0] == domain_filter or r[2] == domain_filter]
    if strength_filter != "All":
        filtered = [r for r in filtered if r[3] == strength_filter]

    c1, c2, c3 = st.columns(3)
    c1.metric("Relationships", len(filtered))
    c2.metric("Strong", sum(1 for r in filtered if r[3] == "Strong"))
    c3.metric("Medium + Weak", sum(1 for r in filtered if r[3] != "Strong"))

    st.divider()

    for f, rel, t, strength, explanation in filtered:
        fM = DOMAIN_META.get(f, {"icon": "📂", "color": "#888"})
        tM = DOMAIN_META.get(t, {"icon": "📂", "color": "#888"})
        sc = STRENGTH_COLORS.get(strength, "#888")
        si = STRENGTH_ICONS.get(strength, "⚪")

        st.markdown(
            f"<div style='border-left:3px solid {sc};padding:8px 14px;margin:5px 0;"
            f"background:white;border-radius:0 6px 6px 0;'>"
            f"<div style='display:flex;align-items:center;gap:8px;flex-wrap:wrap;'>"
            f"<span style='font-weight:bold;color:{fM['color']}'>{fM['icon']} {f}</span>"
            f"<span style='background:#f0f4ff;color:#3949ab;padding:2px 10px;"
            f"border-radius:10px;font-size:11px;font-style:italic'>{rel}</span>"
            f"<span style='font-weight:bold;color:{tM['color']}'>{tM['icon']} {t}</span>"
            f"<span style='margin-left:auto;font-size:11px;color:{sc}'>{si} {strength}</span>"
            f"</div>"
            f"<div style='font-size:11px;color:#666;margin-top:5px'>{explanation}</div>"
            f"</div>",
            unsafe_allow_html=True
        )


def render_graph():
    domains = list(DOMAIN_META.keys())
    n = len(domains)
    positions = {}
    cx, cy, r = 480, 430, 310
    for i, d in enumerate(domains):
        angle = 2 * math.pi * i / n - math.pi / 2
        positions[d] = (cx + r * math.cos(angle), cy + r * math.sin(angle))

    svg_lines = []
    for f, rel, t, strength, explanation in ONTO_RELATIONS:
        if f == t or f not in positions or t not in positions:
            continue
        x1, y1 = positions[f]
        x2, y2 = positions[t]
        color = STRENGTH_COLORS.get(strength, "#ccc")
        w = {"Strong": 3, "Medium": 1.8, "Weak": 1}[strength]
        dash = "" if strength == "Strong" else ('stroke-dasharray="6,3"' if strength == "Medium" else 'stroke-dasharray="3,5"')
        svg_lines.append(
            f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
            f'stroke="{color}" stroke-width="{w}" opacity="0.6" {dash}/>'
        )

    svg_nodes = []
    for d, (x, y) in positions.items():
        meta = DOMAIN_META[d]
        color = meta["color"]
        icon = meta["icon"]
        svg_nodes.append(f'''
        <g>
          <circle cx="{x:.0f}" cy="{y:.0f}" r="46" fill="{color}" opacity="0.12" stroke="{color}" stroke-width="2"/>
          <text x="{x:.0f}" y="{y-14:.0f}" text-anchor="middle" font-size="22">{icon}</text>
          <text x="{x:.0f}" y="{y+4:.0f}" text-anchor="middle" font-size="10" font-weight="bold" fill="{color}">{d}</text>
        </g>''')

    svg = f"""<svg width="960" height="860"
        style="background:white;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,0.08);">
        <defs>
          <marker id="arr-s" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 z" fill="{STRENGTH_COLORS['Strong']}"/>
          </marker>
          <marker id="arr-m" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 z" fill="{STRENGTH_COLORS['Medium']}"/>
          </marker>
          <marker id="arr-w" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 z" fill="{STRENGTH_COLORS['Weak']}"/>
          </marker>
        </defs>
        {''.join(svg_lines)}
        {''.join(svg_nodes)}
        <!-- Legend -->
        <rect x="740" y="20" width="200" height="120" rx="8" fill="white" stroke="#eee"/>
        <text x="755" y="44" font-size="12" font-weight="bold" fill="#333">Relationship strength</text>
        <line x1="755" y1="64" x2="800" y2="64" stroke="{STRENGTH_COLORS['Strong']}" stroke-width="3"/>
        <text x="810" y="68" font-size="11" fill="#555">Strong — causal</text>
        <line x1="755" y1="88" x2="800" y2="88" stroke="{STRENGTH_COLORS['Medium']}" stroke-width="2" stroke-dasharray="6,3"/>
        <text x="810" y="92" font-size="11" fill="#555">Medium — correlational</text>
        <line x1="755" y1="112" x2="800" y2="112" stroke="{STRENGTH_COLORS['Weak']}" stroke-width="1" stroke-dasharray="3,5"/>
        <text x="810" y="116" font-size="11" fill="#555">Weak — future (P3)</text>
    </svg>"""

    components.html(svg, height=880)


def render():
    st.caption(f"{len(ONTO_RELATIONS)} semantic relationships · {len(CAUSAL_CHAINS)} causal chains · 10 domains")
    tab1, tab2, tab3 = st.tabs(["🔗 Causal Chains", "📊 Relations Table", "🌐 Ontology Graph"])
    with tab1:
        render_chains()
    with tab2:
        render_table()
    with tab3:
        render_graph()
