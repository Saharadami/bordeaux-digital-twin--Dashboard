"""
Fetch official commune boundary polygons — Bordeaux Urban Digital Twin
Run this LOCALLY (needs internet access):

    python build_zone_boundaries.py

Downloads each zone's official boundary (GeoJSON) from geo.api.gouv.fr
(French government geo API, free, no key) and writes
sim_assets/zone_boundaries.json. The running app reads this cached file —
it never calls geo.api.gouv.fr at runtime.
"""

import json
import os
import requests

from zones import ZONES

OUT_DIR = os.path.join(os.path.dirname(__file__), "sim_assets")
OUT_PATH = os.path.join(OUT_DIR, "zone_boundaries.json")

API_URL = "https://geo.api.gouv.fr/communes"


def fetch_boundary(insee):
    r = requests.get(
        API_URL,
        params={"code": insee, "fields": "nom,code,contour,centre", "format": "json", "geometry": "contour"},
        timeout=20,
    )
    r.raise_for_status()
    results = r.json()
    if not results:
        raise ValueError(f"No commune found for INSEE code {insee}")
    return results[0]


def main():
    boundaries = {}
    for insee, meta in ZONES.items():
        print(f"Fetching boundary for {meta['name']} ({insee})...")
        c = fetch_boundary(insee)
        boundaries[insee] = {
            "name": c["nom"],
            "insee": c["code"],
            "contour": c["contour"],
            "centre": c["centre"],
        }
        print(f"  OK — {c['contour']['type']}")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(boundaries, f, ensure_ascii=False)
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
