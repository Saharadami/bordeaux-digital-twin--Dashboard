# 🏙️ Bordeaux Urban Digital Twin — Data Patrimony Dashboard

> Master M2 Internship · June – July 2026 · Sahar Adami Kozekonan  
> University of Bordeaux · Complex Systems Engineering

![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=flat&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![Status](https://img.shields.io/badge/Phase%201-Complete-brightgreen?style=flat)

---

## 📌 Overview

A data intelligence platform for the Bordeaux Urban Digital Twin. This repository covers the complete **data infrastructure layer** — catalog, entity model, ontology and live data collectors — built on top of **71 verified datasets** from 20+ open data providers across Bordeaux Métropole.

---

## ✨ Features

**🗄️ Data Catalog**
- 71 datasets · 10 urban domains · direct API links
- Priority classification P1 / P2 / P3
- Driven by a single Excel inventory — no hardcoded data

**🔷 Data Models**
- 45 entities across 4 layers (Static · Time-Series · Aggregated · Junction)
- 18 documented domain relationships with join keys
- Interactive domain graph and relation matrix

**🔗 Ontology**
- 28 semantic relationships (Strong · Medium · Weak)
- 6 causal chains: Traffic→AQ→Health · Rain→Flood→Roads · Weather→Energy · Population→Mobility · Buildings→GHG · Sensors→Twin

**⬇️ Collectors**
- Weather: Open-Meteo API — live, no API key required
- Air quality & Traffic: Phase 2

---

## 🗺️ Domains

| Domain | Datasets | Sources |
|--------|----------|---------|
| 🚗 Mobility | 15 | Bordeaux Métropole DataHub |
| 🌤️ Weather | 14 | Open-Meteo · Copernicus |
| 🌬️ Air quality | 8 | Atmo NA · EEA |
| 🌿 Environment | 7 | EEA · Géorisques |
| 💧 Water | 7 | Vigicrues · EEA |
| ⚡ Energy | 9 | Enedis · RTE · ADEME |
| 🏢 Buildings | 1 | Bordeaux Métropole |
| 👥 Population | 4 | INSEE |
| 📡 Sensors | 2 | Bordeaux Métropole |
| 🌐 Online DataSet | 4 | Bordeaux Métropole |



## 📁 Structure

```
├── app.py                                  # 6-tab dashboard
├── config.py                               # Excel reader
├── Bordeaux_DigitalTwin_Documentation.xlsx # Data inventory
├── domain_relationships.md                 # Relationship documentation
├── pages/
│   ├── overview.py
│   ├── catalog.py
│   ├── data_models.py
│   ├── ontology.py
│   ├── collectors_page.py
│   └── resources.py
├── collectors/
│   ├── weather_collector.py   # ✅ live
│   ├── aq_collector.py        # ⏳ Phase 2
│   └── traffic_collector.py   # ⏳ Phase 2
└── data/
    └── weather/


## 👤 Author

**Sahar Adami Kozekonan**  
M.Sc. Complex Systems Engineering · University of Bordeaux
