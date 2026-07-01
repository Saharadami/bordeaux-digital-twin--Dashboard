"""
Map-matching utilities: snap a raw GPS point onto the nearest point
of a known route polyline (outbound or inbound).

This is a simple nearest-point projection (not a full Hidden Markov Model
map-matcher), but it is accurate enough for tram routes since trams run
on fixed rails and GPS noise is small relative to route point density
(real GTFS shape has 1000+ points over ~15km, i.e. a point every ~13m).
"""
import math


def haversine(lon1, lat1, lon2, lat2):
    """Distance in meters between two lon/lat points."""
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def nearest_point_on_segment(px, py, ax, ay, bx, by):
    """
    Project point P onto segment AB (all in lon/lat, treated as locally
    planar which is fine at city scale). Returns (proj_lon, proj_lat, t)
    where t in [0,1] is the fraction along the segment.
    """
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ax, ay, 0.0
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return ax + t * dx, ay + t * dy, t


def match_point_to_route(lon, lat, route_coords):
    """
    Find the closest point on a route polyline to a given GPS fix.

    Returns dict with:
      - matched_lon, matched_lat : snapped coordinates
      - segment_index            : index of the route segment (0-based)
      - progress                 : 0..1 fraction along the WHOLE route
      - distance_m               : distance from raw GPS to matched point (meters)
    """
    best = None
    n = len(route_coords)

    for i in range(n - 1):
        ax, ay = route_coords[i]
        bx, by = route_coords[i + 1]
        mx, my, t = nearest_point_on_segment(lon, lat, ax, ay, bx, by)
        d = haversine(lon, lat, mx, my)
        if best is None or d < best["distance_m"]:
            best = {
                "matched_lon": mx,
                "matched_lat": my,
                "segment_index": i,
                "segment_t": t,
                "distance_m": d,
            }

    if best is None:
        return None

    best["progress"] = (best["segment_index"] + best["segment_t"]) / (n - 1)
    return best


def match_vehicle(lon, lat, outbound_coords, inbound_coords):
    """
    Try matching against both outbound and inbound routes,
    return whichever is closer, tagged with its direction.
    """
    m_out = match_point_to_route(lon, lat, outbound_coords)
    m_in = match_point_to_route(lon, lat, inbound_coords)

    if m_out is None and m_in is None:
        return None
    if m_in is None or (m_out and m_out["distance_m"] <= m_in["distance_m"]):
        m_out["direction"] = "outbound"
        return m_out
    m_in["direction"] = "inbound"
    return m_in

