"""
Zone registry — Bordeaux Urban Digital Twin
A "zone" is a commune (or later, any custom area) that mobility data can be
scoped to. Starts with Talence; add more communes here as the project grows
to cover more of Bordeaux Métropole.

Boundary polygons are fetched once (see build_zone_boundaries.py) from the
official French government geo API and cached in sim_assets/zone_boundaries.json —
the app never hits the network for this at runtime.
"""

ZONES = {
    "33063": {"name": "Bordeaux", "insee": "33063"},
    "33522": {"name": "Talence", "insee": "33522"},
    "33318": {"name": "Pessac", "insee": "33318"},
}

DEFAULT_ZONE = "33063"
