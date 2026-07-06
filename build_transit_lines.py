"""
Build transit route data (tram + bus) — Bordeaux Urban Digital Twin
Run this LOCALLY (needs access to bdx.mecatran.com):

    python build_transit_lines.py

Downloads TBM's GTFS static feed once and writes sim_assets/transit_lines.json:

{
  "tram": {"A": {"route_id":..., "color":..., "outbound":[[lon,lat],...],
                 "inbound":[...], "stops":[{"id":,"name":,"lat":,"lon":},...]},
           "B": {...}, ...},
  "bus":  {"4": {...}, "20": {...}, ...}   # only bus lines with >=1 stop inside a zone (zones.py)
}

Tram: all 6 lines (A-F), unfiltered — small enough to always show in full.
Bus: TBM runs ~200 bus lines across the whole métropole, so we only keep
lines that actually serve a stop inside one of the configured zones
(see zones.py / geo_utils.py) to keep the live map focused and fast.
"""

import io
import os
import json
import zipfile
import csv
import requests

from zones import ZONES
from geo_utils import point_in_zone

GTFS_URL = (
    "https://bdx.mecatran.com/utw/ws/gtfsfeed/static/bordeaux"
    "?apiKey=opendata-bordeaux-metropole-flux-gtfs-rt"
)

OUT_DIR = os.path.join(os.path.dirname(__file__), "sim_assets")
OUT_PATH = os.path.join(OUT_DIR, "transit_lines.json")

TRAM_LETTERS = ["A", "B", "C", "D", "E", "F"]


def download_gtfs():
    print("Downloading GTFS static feed...")
    r = requests.get(GTFS_URL, timeout=60)
    r.raise_for_status()
    return zipfile.ZipFile(io.BytesIO(r.content))


def read_csv(zf, name):
    with zf.open(name) as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig")
        return list(csv.DictReader(text))


def build_line(route_id, route_color, trips_by_route, shape_points, stops_by_id, stoptimes_by_trip):
    """Returns {route_id, color, outbound, inbound, stops} for one route, or None if no trips."""
    route_trips = trips_by_route.get(route_id, [])
    if not route_trips:
        return None

    shapes_by_dir = {"0": [], "1": []}
    for t in route_trips:
        sid = t.get("shape_id")
        d = t.get("direction_id", "0")
        if sid and sid in shape_points and d in shapes_by_dir:
            shapes_by_dir[d].append(sid)

    def longest_shape(shape_ids):
        if not shape_ids:
            return []
        best = max(set(shape_ids), key=lambda sid: len(shape_points[sid]))
        return [[lon, lat] for _, lon, lat in shape_points[best]]

    outbound = longest_shape(shapes_by_dir["0"])
    inbound = longest_shape(shapes_by_dir["1"])

    seen_stop_ids = set()
    line_stops = []
    # sample a handful of trips (not all, for speed) to collect the stop set
    for t in route_trips[:50]:
        for st in stoptimes_by_trip.get(t["trip_id"], []):
            sid = st["stop_id"]
            if sid in seen_stop_ids or sid not in stops_by_id:
                continue
            seen_stop_ids.add(sid)
            s = stops_by_id[sid]
            line_stops.append({
                "id": sid,
                "name": s.get("stop_name", ""),
                "lat": float(s["stop_lat"]),
                "lon": float(s["stop_lon"]),
            })

    return {
        "route_id": route_id,
        "color": f"#{route_color}" if route_color else None,
        "outbound": outbound,
        "inbound": inbound,
        "stops": line_stops,
    }


def zones_served_by_line(line):
    """List of zone INSEE codes that have >=1 of this line's stops inside them."""
    served = set()
    for s in line["stops"]:
        for insee in ZONES:
            if insee not in served and point_in_zone(s["lon"], s["lat"], insee):
                served.add(insee)
    return served


def main():
    zf = download_gtfs()

    routes = read_csv(zf, "routes.txt")
    trips = read_csv(zf, "trips.txt")
    shapes = read_csv(zf, "shapes.txt")
    stops = read_csv(zf, "stops.txt")
    stop_times = read_csv(zf, "stop_times.txt")

    trips_by_route = {}
    for t in trips:
        trips_by_route.setdefault(t["route_id"], []).append(t)

    shape_points = {}
    for s in shapes:
        shape_points.setdefault(s["shape_id"], []).append(
            (int(s["shape_pt_sequence"]), float(s["shape_pt_lon"]), float(s["shape_pt_lat"]))
        )
    for sid in shape_points:
        shape_points[sid].sort(key=lambda x: x[0])

    stops_by_id = {s["stop_id"]: s for s in stops}

    stoptimes_by_trip = {}
    for st in stop_times:
        stoptimes_by_trip.setdefault(st["trip_id"], []).append(st)
    for tid in stoptimes_by_trip:
        stoptimes_by_trip[tid].sort(key=lambda x: int(x["stop_sequence"]))

    def build(route_id, route_color):
        return build_line(route_id, route_color, trips_by_route, shape_points, stops_by_id, stoptimes_by_trip)

    zone_lines = {insee: {"tram": [], "bus": []} for insee in ZONES}

    # ── Tram: all 6 lines, unfiltered geometry — but still tracked per-zone ──
    tram_result = {}
    tram_routes = {
        r["route_short_name"].strip(): (r["route_id"], r.get("route_color", "").strip())
        for r in routes
        if r.get("route_type") == "0" and r["route_short_name"].strip() in TRAM_LETTERS
    }
    for letter, (route_id, route_color) in tram_routes.items():
        line = build(route_id, route_color)
        if line is None:
            print(f"  [tram {letter}] no trips found, skipping")
            continue
        tram_result[letter] = line
        served = zones_served_by_line(line)
        for insee in served:
            zone_lines[insee]["tram"].append(letter)
        print(f"  [tram {letter}] route_id={route_id} · {len(line['outbound'])+len(line['inbound'])} route points · {len(line['stops'])} stops · zones: {[ZONES[i]['name'] for i in served] or '-'}")

    # ── Bus: only lines serving at least one configured zone ──
    bus_result = {}
    bus_routes = {
        r["route_short_name"].strip(): (r["route_id"], r.get("route_color", "").strip())
        for r in routes
        if r.get("route_type") == "3" and r["route_short_name"].strip()
    }
    print(f"Scanning {len(bus_routes)} bus routes for zone coverage ({', '.join(z['name'] for z in ZONES.values())})...")
    for short_name, (route_id, route_color) in bus_routes.items():
        line = build(route_id, route_color)
        if line is None or not line["stops"]:
            continue
        served = zones_served_by_line(line)
        if served:
            bus_result[short_name] = line
            for insee in served:
                zone_lines[insee]["bus"].append(short_name)
            print(f"  [bus {short_name}] route_id={route_id} · {len(line['stops'])} stops · zones: {[ZONES[i]['name'] for i in served]}")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"tram": tram_result, "bus": bus_result, "zone_lines": zone_lines}, f, ensure_ascii=False)

    print(f"\nWrote {OUT_PATH}")
    print(f"Tram lines: {list(tram_result.keys())}")
    print(f"Bus lines serving configured zones: {list(bus_result.keys())}")
    for insee, zl in zone_lines.items():
        print(f"  {ZONES[insee]['name']}: tram={zl['tram']} · bus={zl['bus']}")


if __name__ == "__main__":
    main()
