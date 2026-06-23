import streamlit as st
from collections import Counter
from config import CATALOG, DOMAIN_META, RELATIONS, get_active_domains

def render():
    active_domains = get_active_domains()
    sources = len(set(d["source"] for d in CATALOG))

    col1, col2, col3 = st.columns(3)
    col1.metric("Domains",  len(active_domains))
    col2.metric("Datasets", len(CATALOG))
    col3.metric("Sources",  sources)

    st.divider()
    st.subheader("Domains")

    counts = Counter(d["domain"] for d in CATALOG)
    selected = st.session_state.get("selected_domain")

    cols = st.columns(5)
    for i, domain in enumerate(active_domains):
        meta = DOMAIN_META.get(domain, {"icon": "📂", "label": domain, "color": "#888"})
        n = counts.get(domain, 0)
        is_selected = selected == domain
        border_style = f"3px solid {meta['color']}" if is_selected else f"2px solid {meta['color']}"
        bg_style = f"{meta['color']}30" if is_selected else f"{meta['color']}12"

        with cols[i % 5]:
            st.markdown(
                f"""
                <div style="
                    border: {border_style};
                    border-radius: 10px;
                    padding: 14px 10px;
                    text-align: center;
                    margin-bottom: 4px;
                    background: linear-gradient(135deg, {bg_style}, transparent);
                    cursor: pointer;
                ">
                    <div style="font-size: 26px;">{meta['icon']}</div>
                    <div style="font-weight:bold; font-size:13px; color:{meta['color']}; margin-top:4px;">
                        {meta['label']}
                    </div>
                    <div style="font-size:22px; font-weight:bold; margin-top:4px;">{n}</div>
                    <div style="font-size:11px; color:#888;">datasets</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("▼" if is_selected else "▶", key=f"btn_{domain}", use_container_width=True):
                if is_selected:
                    st.session_state["selected_domain"] = None
                else:
                    st.session_state["selected_domain"] = domain
                st.rerun()

    # ── Dataset list for selected domain ──
    selected = st.session_state.get("selected_domain")
    if selected:
        meta = DOMAIN_META.get(selected, {"icon": "📂", "label": selected, "color": "#888"})
        st.divider()
        domain_datasets = [d for d in CATALOG if d["domain"] == selected]
        st.markdown(
            f"<h4 style='color:{meta['color']}'>{meta['icon']} {meta['label']} — {len(domain_datasets)} datasets</h4>",
            unsafe_allow_html=True,
        )
        for d in domain_datasets:
            status_icon = "🟢" if d.get("status", "").lower() == "active" else "🟡"
            prio = f" `{d['priority']}`" if d.get("priority") else ""
            with st.expander(f"{status_icon} **{d['name']}**{prio}"):
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Source:** {d['source']}")
                c2.markdown(f"**Format:** `{d['format']}`")
                c3.markdown(f"**Frequency:** {d['frequency']}")
                if d.get("description"):
                    st.markdown(f"📋 {d['description']}")
                if d.get("notes"):
                    st.caption(f"📝 {d['notes']}")
                if d.get("dataset_id"):
                    st.markdown(f"**ID:** `{d['dataset_id']}`")
                if d.get("url"):
                    st.markdown(f"🔗 [Open dataset]({d['url']})")
                if d.get("api_url"):
                    st.code(d["api_url"], language=None)

    st.divider()
    st.subheader("Data architecture")
    steps = [
        ("✅", "Data sources",          "OpenStreetMap · Bordeaux Open Data · Météo France · Atmo NA · TBM · Enedis · Vigicrues…"),
        ("✅", "Data catalog",          f"{len(CATALOG)} datasets · {len(active_domains)} domains · description · fields · API links"),
        ("✅", "Data models",           "TrafficMeasure · WeatherRecord · AirQuality · WaterRecord · EnergyRecord · Building · PopulationZone · Sensor · GreenSpace"),
        ("✅", "Ontology",              f"{len(RELATIONS)} cross-domain semantic relationships"),
        ("⏳", "Database (PostgreSQL)", "Schema design · PostGIS spatial · TimescaleDB time-series"),
        ("⏳", "Data collectors",       "API connectors · schedulers · real-time ingestion"),
        ("⏳", "Feature engineering",   "Normalization · time features · spatial joins"),
        ("⏳", "AI models",             "Traffic prediction · weather · pollution forecasting"),
        ("⏳", "Visualization",         "Heatmaps · time-series · simulation dashboard"),
    ]
    for status, name, desc in steps:
        st.markdown(f"{status} **{name}** — {desc}")
