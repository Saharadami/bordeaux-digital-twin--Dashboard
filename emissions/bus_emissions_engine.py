"""
Bus emissions engine — Bordeaux Urban Digital Twin
Estimates a zone's bus-network CO2/NOx/PM emissions for one typical weekday,
from the *scheduled* GTFS timetable — not live vehicle counts (contrast with
emissions_engine.py, which uses actual car-traffic sensor readings).

Route geometry (for line length) is reused from sim_assets/transit_lines.json,
already downloaded/processed by build_transit_lines.py. Only trips.txt and
calendar.txt are re-fetched live, to count scheduled trips per line on a
representative Monday-Friday service day.
"""

import csv
import io
import json
import os
import zipfile
from math import atan2, cos, radians, sin, sqrt

import requests
import streamlit as st

from emissions.emission_factors import BUS_EMISSION_FACTORS_G_PER_KM, ENERGY_MJ_PER_KM

GTFS_URL = (
    "https://bdx.mecatran.com/utw/ws/gtfsfeed/static/bordeaux"
    "?apiKey=opendata-bordeaux-metropole-flux-gtfs-rt"
)
_LINES_PATH = os.path.join(os.path.dirname(__file__), "..", "sim_assets", "transit_lines.json")


def _haversine_km(lon1, lat1, lon2, lat2):
    r = 6371.0088
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlambda / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def _polyline_km(points):
    return sum(
        _haversine_km(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])
        for i in range(len(points) - 1)
    )


def _line_length_km(line):
    """Average of outbound/inbound shape length — a single representative
    one-way trip length for this line."""
    lengths = [_polyline_km(pts) for pts in (line.get("outbound"), line.get("inbound")) if pts and len(pts) > 1]
    return sum(lengths) / len(lengths) if lengths else 0.0


@st.cache_data(ttl=86400, show_spinner="Fetching GTFS bus schedule...")
def _fetch_weekday_trip_counts():
    """Downloads the live GTFS static feed and returns {route_id: daily_trip_count}
    for bus routes (route_type=3) on one representative weekday (Wednesday).

    TBM's calendar.txt does not give every route a single calendar row flagged
    Monday-through-Friday: weekday service is commonly split across multiple
    service_ids (e.g. a Mon-Wed block and a separate Thu-Fri block), so
    Wednesday is used as the representative day since it falls inside every
    weekday split seen in this feed. Rows are also required to have
    start_date != end_date, which excludes single-day "this week only"
    override entries that would otherwise double-count trips already covered
    by the recurring multi-week service for the same route/day.
    """
    r = requests.get(GTFS_URL, timeout=60)
    r.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(r.content))

    def read_csv(name):
        with zf.open(name) as f:
            return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))

    routes = read_csv("routes.txt")
    trips = read_csv("trips.txt")
    calendar = read_csv("calendar.txt")

    bus_route_ids = {rt["route_id"] for rt in routes if rt.get("route_type") == "3"}

    weekday_service_ids = {
        c["service_id"] for c in calendar
        if c.get("wednesday") == "1" and c.get("saturday") == "0" and c.get("sunday") == "0"
        and c.get("start_date") != c.get("end_date")
    }

    counts = {}
    for t in trips:
        if t["route_id"] in bus_route_ids and t.get("service_id") in weekday_service_ids:
            counts[t["route_id"]] = counts.get(t["route_id"], 0) + 1
    return counts


def compute_bus_emissions_for_zone(zone_insee):
    """Returns None if no bus lines are mapped for this zone, or if the live
    GTFS schedule couldn't be fetched (network/API issue — caller shows a
    warning in that case via bus_fetch_failed()), else:
    {"total_km": float, "CO2_g":, "NOx_g":, "PM_g":, "Energy_MJ":,
     "per_line": [{"code","route_id","daily_trips","length_km","daily_km","share_pct"}, ...]}
    """
    with open(_LINES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    zone_bus_codes = data.get("zone_lines", {}).get(zone_insee, {}).get("bus", [])
    if not zone_bus_codes:
        return None

    try:
        trip_counts = _fetch_weekday_trip_counts()
    except Exception as e:
        st.session_state["_bus_fetch_error"] = str(e)
        return None
    st.session_state.pop("_bus_fetch_error", None)

    per_line = []
    total_km = 0.0
    for code in zone_bus_codes:
        line = data["bus"].get(code)
        if not line:
            continue
        route_id = line["route_id"]
        daily_trips = trip_counts.get(route_id, 0)
        length_km = _line_length_km(line)
        daily_km = daily_trips * length_km
        total_km += daily_km
        per_line.append({
            "code": code, "route_id": route_id, "daily_trips": daily_trips,
            "length_km": length_km, "daily_km": daily_km,
        })

    for row in per_line:
        row["share_pct"] = (row["daily_km"] / total_km * 100) if total_km > 0 else 0.0
    per_line.sort(key=lambda row: row["daily_km"], reverse=True)

    result = {"total_km": total_km, "per_line": per_line}
    for pollutant, factor in BUS_EMISSION_FACTORS_G_PER_KM.items():
        result[f"{pollutant}_g"] = total_km * factor
    result["Energy_MJ"] = total_km * ENERGY_MJ_PER_KM["bus"]
    return result


def bus_fetch_failed():
    """True if the last compute_bus_emissions_for_zone() call in this session
    returned None because the live GTFS fetch raised, not because the zone
    has no mapped bus lines. Lets callers show an accurate message instead of
    the generic 'no bus lines mapped' one."""
    return "_bus_fetch_error" in st.session_state
