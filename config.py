# ── config.py ─────────────────────────────────────────────────────────────────
# Smart config — reads directly from Excel inventory
# To add/update datasets: edit Bordeaux_DigitalTwin_Documentation.xlsx → MASTER sheet
# No code changes needed — dashboard updates automatically

import pandas as pd
import os

# ── Path to Excel inventory ────────────────────────────────────────────────────
_EXCEL_PATH = os.path.join(os.path.dirname(__file__), "Bordeaux_DigitalTwin_Documentation.xlsx")

# ── Domain display metadata (add new domains here when ready) ──────────────────
DOMAIN_META = {
    "Mobility":    {"icon": "🚗", "label": "Mobility & traffic",  "color": "#e8593c"},
    "Weather":     {"icon": "🌤️", "label": "Weather",             "color": "#3b8bd4"},
    "AirQuality":  {"icon": "🌬️", "label": "Air quality",         "color": "#1d9e75"},
    "Environment": {"icon": "🌿", "label": "Environment",          "color": "#3b6d11"},
    "Water":       {"icon": "💧", "label": "Water",               "color": "#0077b6"},
    "Energy":      {"icon": "⚡", "label": "Energy",              "color": "#f4a261"},
    "Buildings":   {"icon": "🏢", "label": "Buildings",           "color": "#ba7517"},
    "Population":  {"icon": "👥", "label": "Population",          "color": "#9b59b6"},
    "Sensors":      {"icon": "📡", "label": "Sensors",            "color": "#e74c3c"},
    "Online DataSet": {"icon": "🌐", "label": "Online DataSet",  "color": "#c0392b"},
}

# ── Load MASTER sheet from Excel ───────────────────────────────────────────────
def _load_catalog():
    try:
        df = pd.read_excel(_EXCEL_PATH, sheet_name="MASTER", dtype=str)
        df = df.fillna("")
        catalog = []
        for _, row in df.iterrows():
            domain = row.get("Domain", "").strip()
            if not domain:
                continue
            catalog.append({
                "domain":       domain,
                "category":     row.get("Category", "").strip(),
                "name":         row.get("Dataset Name", "").strip(),
                "dataset_id":   row.get("Dataset ID", "").strip(),
                "source":       row.get("Provider", "").strip(),
                "description":  row.get("Description", "").strip(),
                "url":          row.get("Dataset URL", "").strip(),
                "api_url":      row.get("API URL", "").strip(),
                "format":       row.get("Format", "").strip(),
                "geometry":     row.get("Geometry", "").strip(),
                "frequency":    row.get("Update Freq.", "").strip(),
                "refresh_rate": row.get("Refresh Rate", "").strip(),
                "temporal":     row.get("Temporal Coverage", "").strip(),
                "spatial":      row.get("Spatial Coverage", "").strip(),
                "license":      row.get("License", "").strip(),
                "status":       row.get("Status", "").strip(),
                "verified":     row.get("Verified", "").strip().lower() == "yes",
                "ai_relevant":  row.get("AI Relevant", "").strip().lower() == "yes",
                "priority":     row.get("Priority", "").strip(),
                "ontology_class": row.get("Ontology Class", "").strip(),
                "source_system":  row.get("Source System", "").strip(),
                "data_owner":     row.get("Data Owner", "").strip(),
                "notes":          row.get("Notes", "").strip(),
                "type": "Open data" if "ouverte" in row.get("License", "").lower()
                         or "open" in row.get("License", "").lower()
                         or "odbl" in row.get("License", "").lower()
                         else "API" if row.get("API URL", "").strip()
                         else "Other",
            })
        return catalog
    except Exception as e:
        print(f"[config] ERROR loading Excel: {e}")
        return []

# ── Public CATALOG ─────────────────────────────────────────────────────────────
CATALOG = _load_catalog()

# ── Helper: domains that actually have data ────────────────────────────────────
def get_active_domains():
    """Returns only domains that have at least 1 dataset in the inventory."""
    seen = []
    for d in CATALOG:
        if d["domain"] not in seen:
            seen.append(d["domain"])
    return seen

# ── Data Models — only for domains with data ───────────────────────────────────
# Add a new entity block when you have real datasets for that domain
MODELS = {
    "TrafficMeasure": {
        "color": "#e8593c",
        "description": "Real-time and historical traffic measurements per sensor/road segment",
        "domains": ["Mobility"],
        "fields": [
            ("traffic_id",      "BIGSERIAL",    "PK"),
            ("road_id",         "VARCHAR(50)",  "FK → RoadSegment"),
            ("sensor_id",       "VARCHAR(50)",  "FK → Sensor"),
            ("timestamp",       "TIMESTAMPTZ",  "TimescaleDB"),
            ("vehicle_count",   "INTEGER",      ""),
            ("avg_speed_kmh",   "FLOAT",        ""),
            ("congestion_index","FLOAT",        "0-1"),
        ],
    },
    "WeatherRecord": {
        "color": "#3b8bd4",
        "description": "Hourly weather observations and forecasts",
        "domains": ["Weather"],
        "fields": [
            ("weather_id",       "BIGSERIAL",   "PK"),
            ("station_id",       "VARCHAR(50)", "FK → Sensor"),
            ("timestamp",        "TIMESTAMPTZ", "TimescaleDB"),
            ("temperature_c",    "FLOAT",       ""),
            ("humidity_pct",     "FLOAT",       ""),
            ("precipitation_mm", "FLOAT",       ""),
            ("wind_speed_ms",    "FLOAT",       ""),
        ],
    },
    "AirQuality": {
        "color": "#1d9e75",
        "description": "Air quality measurements per monitoring station",
        "domains": ["AirQuality"],
        "fields": [
            ("aq_id",       "BIGSERIAL",   "PK"),
            ("station_id",  "VARCHAR(50)", "FK → Sensor"),
            ("timestamp",   "TIMESTAMPTZ", "TimescaleDB"),
            ("pm25",        "FLOAT",       "µg/m³"),
            ("pm10",        "FLOAT",       "µg/m³"),
            ("no2",         "FLOAT",       "µg/m³"),
            ("o3",          "FLOAT",       "µg/m³"),
            ("aqi",         "INTEGER",     "0-500"),
        ],
    },
    "WaterRecord": {
        "color": "#0077b6",
        "description": "River level, flood alerts and hydrographic data",
        "domains": ["Water"],
        "fields": [
            ("water_id",       "BIGSERIAL",   "PK"),
            ("station_id",     "VARCHAR(50)", "FK → Sensor"),
            ("timestamp",      "TIMESTAMPTZ", "TimescaleDB"),
            ("river_level_cm", "FLOAT",       ""),
            ("flow_m3s",       "FLOAT",       ""),
            ("flood_alert",    "VARCHAR(10)", "green/yellow/orange/red"),
        ],
    },
    "EnergyRecord": {
        "color": "#f4a261",
        "description": "Electricity consumption, solar production and grid carbon intensity",
        "domains": ["Energy"],
        "fields": [
            ("energy_id",       "BIGSERIAL",   "PK"),
            ("zone_id",         "VARCHAR(50)", "FK → PopulationZone"),
            ("timestamp",       "TIMESTAMPTZ", "TimescaleDB"),
            ("consumption_kwh", "FLOAT",       ""),
            ("solar_prod_kwh",  "FLOAT",       ""),
            ("carbon_gco2kwh",  "FLOAT",       "gCO2eq/kWh"),
        ],
    },
    "PopulationZone": {
        "color": "#9b59b6",
        "description": "IRIS-level population and social indicators",
        "domains": ["Population"],
        "fields": [
            ("iris_code",       "VARCHAR(20)", "PK"),
            ("iris_name",       "VARCHAR(100)",""),
            ("population",      "INTEGER",     ""),
            ("density_per_km2", "FLOAT",       ""),
            ("median_income",   "FLOAT",       ""),
            ("geometry",        "GEOMETRY",    "PostGIS Polygon"),
        ],
    },
    "Building": {
        "color": "#ba7517",
        "description": "Building footprints, DPE energy class and land transactions",
        "domains": ["Buildings"],
        "fields": [
            ("building_id", "VARCHAR(50)", "PK"),
            ("iris_code",   "VARCHAR(20)", "FK → PopulationZone"),
            ("height_m",    "FLOAT",       ""),
            ("dpe_class",   "CHAR(1)",     "A-G"),
            ("build_year",  "INTEGER",     ""),
            ("geometry",    "GEOMETRY",    "PostGIS Polygon"),
        ],
    },
    "GreenSpace": {
        "color": "#3b6d11",
        "description": "Tree cover density and environmental features",
        "domains": ["Environment"],
        "fields": [
            ("space_id",   "SERIAL",       "PK"),
            ("space_type", "VARCHAR(50)",  ""),
            ("area_m2",    "FLOAT",        ""),
            ("canopy_pct", "FLOAT",        ""),
            ("geometry",   "GEOMETRY",     "PostGIS Polygon"),
        ],
    },
    "Sensor": {
        "color": "#e74c3c",
        "description": "All physical sensors: traffic, AQ, meteo, hydro",
        "domains": ["Sensors", "Mobility", "AirQuality", "Water"],
        "fields": [
            ("sensor_id",   "VARCHAR(50)", "PK"),
            ("sensor_type", "VARCHAR(30)", "traffic/aq/meteo/hydro"),
            ("name",        "VARCHAR(100)",""),
            ("lat",         "FLOAT",       ""),
            ("lon",         "FLOAT",       ""),
            ("status",      "VARCHAR(20)", ""),
        ],
    },
}

# ── Ontology Relations — only between domains that have data ───────────────────
RELATIONS = [
    # (From, Relationship, To, Explanation, Strength)
    ("Weather",      "drives",               "AirQuality",   "Wind and rain disperse or concentrate pollutants",        "Strong"),
    ("Weather",      "impacts",              "Water",        "Precipitation drives river level and flood risk",          "Strong"),
    ("Weather",      "influences",           "Energy",       "Temperature drives heating/cooling demand",               "Strong"),
    ("Weather",      "affects",              "Mobility",     "Rain and fog reduce speed and increase accidents",        "Strong"),
    ("AirQuality",   "health impact on",     "Population",   "PM2.5 and NO2 cause respiratory illness",                 "Strong"),
    ("Mobility",     "generates",            "AirQuality",   "Vehicle emissions are primary NO2 and PM source",        "Strong"),
    ("Energy",       "carbon linked to",     "AirQuality",   "Grid carbon intensity affects urban GHG footprint",       "Medium"),
    ("Population",   "drives demand for",    "Energy",       "Population density determines energy consumption",        "Strong"),
    ("Population",   "drives demand for",    "Mobility",     "Commuting patterns define traffic volume",                "Strong"),
    ("Buildings",    "determines",           "Energy",       "DPE class and surface define energy needs",               "Strong"),
    ("Buildings",    "located in",           "Population",   "Buildings linked to IRIS population zones",               "Strong"),
    ("Water",        "flood risk affects",   "Mobility",     "Garonne floods close roads and disrupt transport",        "Strong"),
    ("Environment",  "regulates",            "AirQuality",   "Tree cover absorbs CO2 and PM — urban green buffer",     "Medium"),
    ("Environment",  "mitigates",            "Water",        "Green infrastructure absorbs rainwater runoff",           "Medium"),
    ("Sensors",      "feeds data to",        "Mobility",     "Traffic sensors provide real-time flow data",             "Strong"),
    ("Sensors",      "feeds data to",        "AirQuality",   "AQ stations provide PM2.5, NO2, O3 measurements",       "Strong"),
    ("Sensors",      "feeds data to",        "Water",        "Hydro stations monitor Garonne level and flow",           "Strong"),
]
