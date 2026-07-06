"""
Geo filtering utilities — Bordeaux Urban Digital Twin
Generic helpers to scope Bordeaux-Métropole-wide datasets down to a single
zone (commune), so the same code works for Talence today and any other
commune added to zones.py later.
"""

import json
import os

_BOUNDARIES_PATH = os.path.join(os.path.dirname(__file__), "sim_assets", "zone_boundaries.json")

_boundaries_cache = None


def _load_boundaries():
    global _boundaries_cache
    if _boundaries_cache is None:
        with open(_BOUNDARIES_PATH, "r", encoding="utf-8") as f:
            _boundaries_cache = json.load(f)
    return _boundaries_cache


def get_zone_boundary(insee):
    """Returns the zone's GeoJSON geometry (Polygon or MultiPolygon)."""
    return _load_boundaries()[insee]["contour"]


def get_zone_centre(insee):
    """Returns [lon, lat] of the zone's centroid."""
    return _load_boundaries()[insee]["centre"]["coordinates"]


def get_zone_bounds(insee):
    """Returns [[min_lon, min_lat], [max_lon, max_lat]] — the bounding box of
    the zone's boundary, for fitting a map view exactly to that zone."""
    geometry = get_zone_boundary(insee)
    if geometry["type"] == "Polygon":
        outer_rings = [geometry["coordinates"][0]]
    else:  # MultiPolygon
        outer_rings = [poly[0] for poly in geometry["coordinates"]]
    lons = [pt[0] for ring in outer_rings for pt in ring]
    lats = [pt[1] for ring in outer_rings for pt in ring]
    return [[min(lons), min(lats)], [max(lons), max(lats)]]


def _point_in_ring(lon, lat, ring):
    """Ray-casting point-in-polygon test against a single [lon,lat] ring."""
    inside = False
    n = len(ring)
    x, y = lon, lat
    x1, y1 = ring[0]
    for i in range(1, n + 1):
        x2, y2 = ring[i % n]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1):
            inside = not inside
        x1, y1 = x2, y2
    return inside


def point_in_geometry(lon, lat, geometry):
    """Point-in-polygon test supporting GeoJSON Polygon and MultiPolygon.
    Only the outer ring of each polygon is checked (holes are ignored —
    fine for commune boundaries, which are simple exteriors)."""
    gtype = geometry["type"]
    if gtype == "Polygon":
        return _point_in_ring(lon, lat, geometry["coordinates"][0])
    if gtype == "MultiPolygon":
        return any(_point_in_ring(lon, lat, poly[0]) for poly in geometry["coordinates"])
    raise ValueError(f"Unsupported geometry type: {gtype}")


def point_in_zone(lon, lat, insee):
    return point_in_geometry(lon, lat, get_zone_boundary(insee))


def filter_records_by_point(records, insee, lon_field, lat_field):
    """Keep only records whose (lon, lat) falls inside the zone's boundary."""
    boundary = get_zone_boundary(insee)
    return [
        r for r in records
        if r.get(lon_field) is not None and r.get(lat_field) is not None
        and point_in_geometry(float(r[lon_field]), float(r[lat_field]), boundary)
    ]


def filter_records_by_field(records, insee, field, zone_name=None):
    """Keep only records whose `field` (commune name or INSEE code) matches the zone.
    Matches against either the commune name or its INSEE code, whichever the
    dataset happens to expose."""
    zone_name = zone_name or _load_boundaries()[insee]["name"]
    targets = {insee, zone_name.lower()}
    return [r for r in records if str(r.get(field, "")).strip().lower() in targets or str(r.get(field, "")).strip() == insee]
