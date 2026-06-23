import streamlit as st
import pandas as pd
from config import CATALOG, DOMAIN_META, get_active_domains

def render():
    active_domains = get_active_domains()

    if st.session_state.get("goto_catalog") and "selected_domain" in st.session_state:
        default_domain = st.session_state["selected_domain"]
        st.session_state["goto_catalog"] = False
    else:
        default_domain = "All"

    domains_list = ["All"] + active_domains
    categories = ["All"] + sorted(set(d["category"] for d in CATALOG if d.get("category")))
    priorities = ["All"] + sorted(set(d["priority"] for d in CATALOG if d.get("priority")))

    default_idx = domains_list.index(default_domain) if default_domain in domains_list else 0

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        selected_domain = st.selectbox("Domain", domains_list, index=default_idx)
    with col2:
        selected_cat = st.selectbox("Category", categories)
    with col3:
        selected_prio = st.selectbox("Priority", priorities)

    filtered = CATALOG.copy()
    if selected_domain != "All":
        filtered = [d for d in filtered if d["domain"] == selected_domain]
    if selected_cat != "All":
        filtered = [d for d in filtered if d.get("category") == selected_cat]
    if selected_prio != "All":
        filtered = [d for d in filtered if d.get("priority") == selected_prio]

    c1, c2, c3 = st.columns(3)
    c1.metric("Datasets", len(filtered))
    c2.metric("Sources",  len(set(d["source"] for d in filtered)))
    c3.metric("Formats",  len(set(d["format"] for d in filtered)))

    st.divider()

    for d in filtered:
        meta = DOMAIN_META.get(d["domain"], {"icon": "📂"})
        status_icon = "🟢" if d.get("status", "").lower() == "active" else "🟡"
        prio_badge = f" · `{d['priority']}`" if d.get("priority") else ""
        title = f"{status_icon} {meta['icon']} **{d['domain']}** · {d['name']}{prio_badge}"

        with st.expander(title):
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"**Provider:** {d['source']}")
            c2.markdown(f"**Format:** `{d['format']}`")
            c3.markdown(f"**Frequency:** {d['frequency']}")
            c4.markdown(f"**Category:** {d.get('category','')}")

            if d.get("description"):
                st.markdown(f"📋 {d['description']}")

            row2 = st.columns(4)
            if d.get("temporal"):
                row2[0].markdown(f"**Period:** {d['temporal']}")
            if d.get("spatial"):
                row2[1].markdown(f"**Coverage:** {d['spatial']}")
            if d.get("geometry"):
                row2[2].markdown(f"**Geometry:** `{d['geometry']}`")
            if d.get("license"):
                row2[3].markdown(f"**License:** {d['license']}")

            if d.get("notes"):
                st.caption(f"📝 {d['notes']}")

            if d.get("dataset_id"):
                st.markdown(f"**Dataset ID:** `{d['dataset_id']}`")

            btn_cols = st.columns(2)
            if d.get("url"):
                btn_cols[0].markdown(f"🔗 [Open dataset page]({d['url']})")
            if d.get("api_url"):
                with btn_cols[1].expander("API URL"):
                    st.code(d["api_url"], language=None)

    st.caption(f"{len(filtered)} datasets shown")
