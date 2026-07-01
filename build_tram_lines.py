"""
Build multi-line tram route data — Bordeaux Urban Digital Twin
Run this LOCALLY (needs access to bdx.mecatran.com):

    python build_tram_lines.py

Downloads TBM's GTFS static feed, extracts the 6 tram lines (A-F),
and writes sim_assets/tram_all_lines.json with the same structure
already used for tramB_route_data.json — but one entry per line:

{
  "A": {"route_id": "...", "outbound": [[lon,lat], ...], "inbound": [...],
        "stops": [{"id":..., "name":..., "lat":..., "lon":...}, ...]},
  "B": {...}, "C": {...}, "D": {...}, "E": {...}, "F": {...}
}
"""

import io
import os
import zipfile
import csv
import requests

GTFS_URL = (
    "https://bdx.mecatran.com/utw/ws/gtfsfeed/static/bordeaux"
    "?apiKey=opendata-bordeaux-metropole-flux-gtfs-rt"
)

OUT_DIR = os.path.join(os.path.dirname(__file__), "sim_assets")
OUT_PATH = os.path.join(OUT_DIR, "tram_all_lines.json")

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


def main():
    zf = download_gtfs()

    routes = read_csv(zf, "routes.txt")
    trips = read_csv(zf, "trips.txt")
    shapes = read_csv(zf, "shapes.txt")
    stops = read_csv(zf, "stops.txt")
    stop_times = read_csv(zf, "stop_times.txt")

    # route_type == 0 -> tram (GTFS standard). Match tram lines by short name A-F.
    tram_routes = {
        r["route_short_name"].strip(): (r["route_id"], r.get("route_color", "").strip())
        for r in routes
        if r.get("route_type") == "0" and r["route_short_name"].strip() in TRAM_LETTERS
    }
    print(f"Found tram routes: {tram_routes}")

    # trips per route_id
    trips_by_route = {}
    for t in trips:
        trips_by_route.setdefault(t["route_id"], []).append(t)

    # shape points grouped by shape_id, sorted by sequence
    shape_points = {}
    for s in shapes:
        shape_points.setdefault(s["shape_id"], []).append(
            (int(s["shape_pt_sequence"]), float(s["shape_pt_lon"]), float(s["shape_pt_lat"]))
        )
    for sid in shape_points:
        shape_points[sid].sort(key=lambda x: x[0])

    # stops lookup
    stops_by_id = {s["stop_id"]: s for s in stops}

    # stop_times grouped by trip_id, sorted by sequence
    stoptimes_by_trip = {}
    for st in stop_times:
        stoptimes_by_trip.setdefault(st["trip_id"], []).append(st)
    for tid in stoptimes_by_trip:
        stoptimes_by_trip[tid].sort(key=lambda x: int(x["stop_sequence"]))

    result = {}

    for letter, (route_id, route_color) in tram_routes.items():
        route_trips = trips_by_route.get(route_id, [])
        if not route_trips:
            print(f"  [{letter}] no trips found, skipping")
            continue

        # group trip shape_ids by direction_id, pick the longest shape per direction
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

        # unique stops actually served by this route's trips
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

        result[letter] = {
            "route_id": route_id,
            "color": f"#{route_color}" if route_color else None,
            "outbound": outbound,
            "inbound": inbound,
            "stops": line_stops,
        }
        print(f"  [{letter}] route_id={route_id} · {len(outbound)+len(inbound)} route points · {len(line_stops)} stops")

    os.makedirs(OUT_DIR, exist_ok=True)
    import json
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)

    print(f"\nWrote {OUT_PATH}")
    print(f"Lines built: {list(result.keys())}")


if __name__ == "__main__":
    main()