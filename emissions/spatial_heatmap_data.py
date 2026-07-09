"""
Spatial heatmap data — Bordeaux Urban Digital Twin
Thin join layer for the 🔥 Emission Heatmap tab: no new emission math — reuses
emissions_engine.py (Car) and bus_emissions_engine.py (Bus), joining their
already-computed pollutant totals with geometry already used elsewhere in the
app (sensor "Geo Point" for Car, GTFS line shapes for Bus).
"""

import json
import os

import pandas as pd

from emissions.emissions_engine import compute_emissions, SENSOR_COL
from emissions.bus_emissions_engine import compute_bus_emissions_for_zone
from emissions.emission_factors import BUS_EMISSION_FACTORS_G_PER_KM

_LINES_PATH = os.path.join(os.path.dirname(__file__), "..", "sim_assets", "transit_lines.json")

POLLUTANTS = ("CO2", "NOx", "PM")


def car_heatmap_points(csv_path, pollutant="CO2"):
    """Returns a list of {"lat", "lon", "intensity"} dicts, one per sensor —
    intensity is the *average daily* total of the chosen pollutant for that
    sensor (sum over the fetched CSV / number of distinct days in it). Zones
    have different fetched history lengths (e.g. Bordeaux ~26 days vs Talence
    ~40), so a raw multi-day sum would make longer-history zones look
    artificially "hotter" even at equal daily pollution — averaging per day
    puts every zone on the same footing."""
    col = f"{pollutant}_g"
    emissions_df = compute_emissions(csv_path)
    n_days = emissions_df["date"].dt.floor("D").nunique() or 1
    totals = emissions_df.groupby("sensor_id")[col].sum() / n_days

    raw = pd.read_csv(csv_path)
    geo = raw["Geo Point"].astype(str).str.split(",", n=1, expand=True)
    raw["_lat"] = pd.to_numeric(geo[0], errors="coerce")
    raw["_lon"] = pd.to_numeric(geo[1], errors="coerce")
    coords = raw.dropna(subset=["_lat", "_lon"]).groupby(SENSOR_COL)[["_lat", "_lon"]].first()

    joined = totals.to_frame("intensity").join(coords, how="inner")
    return [
        {"lat": float(row["_lat"]), "lon": float(row["_lon"]), "intensity": float(row["intensity"])}
        for _, row in joined.iterrows()
        if row["intensity"] > 0
    ]


def bus_emission_lines(zone_insee, pollutant="CO2"):
    """Returns a list of {"code", "coords": [[lat, lon], ...], "value"} dicts,
    one per bus line serving the zone — value is that line's *daily* total
    for the chosen pollutant (same figure as "Bus lines by estimated daily
    CO2"), geometry is the same GTFS shape the live map draws.

    Already a single-day figure by construction (compute_bus_emissions_for_zone
    estimates one representative weekday from the GTFS schedule, not a sum
    over multiple fetched days like Car) — no averaging needed here, unlike
    car_heatmap_points()."""
    result = compute_bus_emissions_for_zone(zone_insee)
    if result is None:
        return []
    factor = BUS_EMISSION_FACTORS_G_PER_KM[pollutant]

    with open(_LINES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    lines = []
    for row in result["per_line"]:
        line = data["bus"].get(row["code"])
        if not line:
            continue
        points = line.get("outbound") or line.get("inbound") or []
        if len(points) < 2:
            continue
        coords = [[lat, lon] for lon, lat in points]  # GeoJSON [lon,lat] -> Leaflet [lat,lon]
        lines.append({
            "code": row["code"],
            "coords": coords,
            "value": row["daily_km"] * factor,
        })
    return lines
