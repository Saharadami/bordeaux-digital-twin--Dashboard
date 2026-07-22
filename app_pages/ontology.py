import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network
from app_pages.data_models import RELATIONS, P3_RELATIONS

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


_EDGE_DASHES = {"Strong": False, "Medium": [8, 4], "Weak": [2, 4]}
_EDGE_WIDTH  = {"Strong": 3.5, "Medium": 2, "Weak": 1}
_DIM_COLOR = "#e2e2e2"
_DIM_EDGE_COLOR = "#dddddd"
_DIM_FONT_COLOR = "#bbbbbb"


def _build_domain_graph_html(selected_domain=None):
    domains = list(DOMAIN_META.keys())
    highlight_active = selected_domain in domains

    neighbors = set()
    if highlight_active:
        neighbors.add(selected_domain)
        for f, rel, t, strength, explanation in ONTO_RELATIONS:
            if f == t or f not in domains or t not in domains:
                continue
            if f == selected_domain:
                neighbors.add(t)
            elif t == selected_domain:
                neighbors.add(f)

    net = Network(height="950px", width="100%", directed=True,
                  bgcolor="#ffffff", font_color="#333333", cdn_resources="in_line")
    net.barnes_hut(gravity=-4200, central_gravity=0.1, spring_length=300,
                    spring_strength=0.015, damping=0.2, overlap=0.7)

    for d in domains:
        meta = DOMAIN_META[d]
        p1_total = sum(count for f, t, p, count, *_ in RELATIONS if p == "P1" and (f == d or t == d))
        is_dim = highlight_active and d not in neighbors
        is_selected = highlight_active and d == selected_domain
        net.add_node(
            d,
            label=f"{meta['icon']} {d}\n{p1_total} P1 links",
            title=f"{d} — {p1_total} P1 relationship links",
            color={
                "background": _DIM_COLOR if is_dim else meta["color"],
                "border": "#cccccc" if is_dim else meta["color"],
            },
            size=18 + p1_total * 1.4,
            font={"size": 13, "face": "arial", "color": _DIM_FONT_COLOR if is_dim else "#222222"},
            borderWidth=4 if is_selected else 2,
        )

    for f, rel, t, strength, explanation in ONTO_RELATIONS:
        if f == t or f not in domains or t not in domains:
            continue
        touches_selected = highlight_active and (f == selected_domain or t == selected_domain)
        is_dim = highlight_active and not touches_selected
        net.add_edge(
            f, t,
            label=rel,
            title=explanation,
            color=_DIM_EDGE_COLOR if is_dim else STRENGTH_COLORS.get(strength, "#999"),
            width=1 if is_dim else _EDGE_WIDTH.get(strength, 1.5),
            dashes=_EDGE_DASHES.get(strength, False),
            arrows="to",
            font={"size": 9, "color": _DIM_FONT_COLOR if is_dim else "#444444",
                  "strokeWidth": 3, "strokeColor": "#ffffff", "align": "middle"},
            smooth={"type": "dynamic"},
        )

    net.set_options("""
    {
      "interaction": {"hover": true, "tooltipDelay": 120},
      "physics": {"stabilization": {"iterations": 300}}
    }
    """)

    html = net.generate_html()
    # Streamlit's st.tabs() renders every tab's content on every run, hidden
    # tabs included — so this component's iframe often first mounts while its
    # container is display:none. vis-network measures canvas size once at
    # that point and never re-measures on its own, so switching to this tab
    # later shows everything crammed at (0,0). A plain fit()-after-load isn't
    # enough: it still measures a zero-size canvas. A ResizeObserver on the
    # container catches the display:none -> visible transition (a real size
    # change) and forces a redraw + fit at that moment; stabilizationIterationsDone
    # plus a poll are backup triggers for the same fit. Physics is left running
    # (not frozen) so barnes_hut keeps relaxing the layout after the initial burst.
    fit_script = """
    <script type="text/javascript">
    window.addEventListener('load', function () {
        function whenNetworkReady(cb, attemptsLeft) {
            if (typeof network !== 'undefined' && network) { cb(); return; }
            if (attemptsLeft > 0) setTimeout(function () { whenNetworkReady(cb, attemptsLeft - 1); }, 100);
        }
        whenNetworkReady(function () {
            var container = document.getElementById('mynetwork');

            function settle() {
                network.redraw();
                network.fit({ animation: false });
            }

            network.once('stabilizationIterationsDone', settle);

            if (window.ResizeObserver && container) {
                var ro = new ResizeObserver(function (entries) {
                    for (var i = 0; i < entries.length; i++) {
                        if (entries[i].contentRect.width > 0 && entries[i].contentRect.height > 0) {
                            settle();
                        }
                    }
                });
                ro.observe(container);
            }

            var tries = 0;
            var poll = setInterval(function () {
                tries++;
                if (container && container.clientWidth > 0) settle();
                if (tries > 20) clearInterval(poll);
            }, 300);
        }, 30);
    });
    </script>
    """
    html = html.replace("</body>", fit_script + "</body>")
    return html


def _legend_svg():
    return f"""<svg width="200" height="130" style="background:white;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,0.08);">
        <rect x="0" y="0" width="200" height="120" rx="8" fill="white" stroke="#eee"/>
        <text x="15" y="24" font-size="12" font-weight="bold" fill="#333">Relationship strength</text>
        <line x1="15" y1="44" x2="60" y2="44" stroke="{STRENGTH_COLORS['Strong']}" stroke-width="3"/>
        <text x="70" y="48" font-size="11" fill="#555">Strong — causal</text>
        <line x1="15" y1="68" x2="60" y2="68" stroke="{STRENGTH_COLORS['Medium']}" stroke-width="2" stroke-dasharray="8,4"/>
        <text x="70" y="72" font-size="11" fill="#555">Medium — correlational</text>
        <line x1="15" y1="92" x2="60" y2="92" stroke="{STRENGTH_COLORS['Weak']}" stroke-width="1" stroke-dasharray="2,4"/>
        <text x="70" y="96" font-size="11" fill="#555">Weak — future (P3)</text>
    </svg>"""


def render_graph():
    graph_area = st.container()

    st.divider()
    st.markdown("**Select a domain to see its relationships:**")

    selected_domain = st.selectbox(
        "Domain",
        ["— select —"] + list(DOMAIN_META.keys()),
        key="graph_domain_select"
    )
    selected = selected_domain if selected_domain != "— select —" else None

    with graph_area:
        col_graph, col_legend = st.columns([4, 1])
        with col_graph:
            components.html(_build_domain_graph_html(selected), height=970, scrolling=False)
        with col_legend:
            components.html(_legend_svg(), height=140)

    if selected:
        dM = DOMAIN_META[selected]
        rels = [(f, t, p, count, short, bullets, datasets, join)
                for f, t, p, count, short, bullets, datasets, join in RELATIONS
                if f == selected or t == selected]

        st.markdown(
            f"<div style='border-left:4px solid {dM['color']};padding-left:12px;margin:10px 0;'>"
            f"<strong style='font-size:16px;color:{dM['color']}'>{dM['icon']} {selected}</strong>"
            f"<span style='font-size:12px;color:#888;margin-left:8px;'>{len(rels)} P1 relationship group(s)</span>"
            f"</div>",
            unsafe_allow_html=True
        )

        for f, t, p, count, short, bullets, datasets, join in rels:
            other = t if f == selected else f
            other_meta = DOMAIN_META.get(other, {"color": "#888", "icon": "📂"})
            isSelf = f == t
            border = dM["color"] if isSelf else other_meta["color"]
            label = f"{dM['icon']} {selected} ↔ (internal)" if isSelf else f"{dM['icon']} {selected} → {other_meta['icon']} {other}"

            with st.expander(f"{label}  —  P1·{count} · {short}"):
                for b in bullets:
                    st.markdown(f"&nbsp;&nbsp;{b}")
                st.markdown("**Datasets:** " + " · ".join([f"`{d}`" for d in datasets]))
                st.markdown(f"**Join key:** `{join}`")

        p3rels = [(f, t, desc) for f, t, desc in P3_RELATIONS
                  if f == selected or t == selected]
        if p3rels:
            st.markdown("**Future development — P3:**")
            for f, t, desc in p3rels:
                other = t if f == selected else f
                oM = DOMAIN_META.get(other, {"icon": "📂"})
                st.markdown(f"&nbsp;&nbsp;{oM['icon']} **{other}**: {desc}")


def render():
    st.caption(f"{len(ONTO_RELATIONS)} semantic relationships · {len(CAUSAL_CHAINS)} causal chains · 10 domains")
    tab1, tab2, tab3 = st.tabs(["🔗 Causal Chains", "📊 Relations Table", "🌐 Ontology Graph"])
    with tab1:
        render_chains()
    with tab2:
        render_table()
    with tab3:
        render_graph()