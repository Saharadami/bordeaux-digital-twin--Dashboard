"""
Heat dispersion engine — Bordeaux Urban Digital Twin
Solves a simplified 2D advection-diffusion PDE (finite difference) for
traffic-derived waste heat over a zone's bounding box. See
dispersion/heat_dispersion_spec.md for the equation, sources for D/k, and
disclosed limitations.

No new emission/energy math: reuses emissions_engine.compute_emissions(),
bus_emissions_engine.compute_bus_emissions_for_zone() and
emission_factors.ENERGY_MJ_PER_KM for the source term, and
collectors.weather_collector for the hourly wind field.
"""

import json
import math
import os

import numpy as np
import pandas as pd
import streamlit as st

from geo_utils import get_zone_bounds, get_zone_centre
from emissions.emissions_engine import compute_emissions, SENSOR_COL
from emissions.bus_emissions_engine import compute_bus_emissions_for_zone
from emissions.emission_factors import ENERGY_MJ_PER_KM
from collectors.weather_collector import get_latest_file

GRID_N = 50  # cells per side — fixed in code, not exposed in UI (see spec §4)

# D — eddy diffusivity, m²/s. Sourced range for atmospheric eddy diffusivity is
# ~10-100 m²/s; 15 is an engineering choice near the low end of that range
# because this domain is near-surface (not full daytime convective boundary
# layer bulk mixing) — an engineering choice inside a sourced range, not a
# calibrated value. See spec §3.
D_EDDY_M2S = 15.0

# k — vertical loss coefficient, derived (not directly sourced) from urban
# mixing-height literature: H_MIX_M is a conservative average of the sourced
# 300-500m evening/off-peak range, W_ENTRAINMENT_MS from a ~170 m/h mixed-layer
# growth rate. See spec §3.
_H_MIX_M = 400.0
_W_ENTRAINMENT_MS = 0.047
K_LOSS_S = _W_ENTRAINMENT_MS / _H_MIX_M  # ~1.2e-4 s^-1, half-life ~100 min

_M_PER_DEG_LAT = 111_320.0  # standard equirectangular constant, WGS84

_LINES_PATH = os.path.join(os.path.dirname(__file__), "..", "sim_assets", "transit_lines.json")

CFL_SAFETY_FACTOR = 0.9  # conventional margin below the theoretical CFL limit

# Ensemble parameters — see spec §2.5 for why this replaced the earlier
# continuous 24-hour accumulation (that architecture homogenized the whole
# domain well before 24h regardless of D/k within the sourced ranges: local
# diffusion between source cells took ~1.6h and wind crossed the whole domain
# in well under an hour, so every member of an hour-by-hour sequence ended up
# smeared). Each ensemble member is now solved independently to quasi-steady
# state instead.
_ENSEMBLE_STEP = 3     # subsample every 3rd hourly weather record (~64 of 192)

# Spin-up duration is deliberately an early NEAR-FIELD snapshot, not a run to
# full equilibrium: a sweep during development showed max/mean localization
# in the resulting mean_grid decays monotonically with spin-up length (~4.0
# at 1h, ~2.8 at 1.6h, ~2.4 at 2h, ~1.6 at 6h/near-equilibrium) because the
# true steady state of this system, at this domain scale with D=15 and
# k's ~100min half-life, is itself close to spatially uniform — more
# spin-up time doesn't reveal hidden structure, it erases the structure
# that IS there. 1.6h ~= the local diffusion timescale between neighboring
# source cells (see spec §2.5) is used as a physically-anchored point that
# still keeps local hot spots visible (max/mean ~2.8) — see spec §2.5 for
# the full sweep table and the reasoning for choosing an early snapshot
# over full equilibrium.
_SPINUP_HOURS = 1.6


def _build_grid(zone_insee, n=GRID_N):
    (min_lon, min_lat), (max_lon, max_lat) = get_zone_bounds(zone_insee)
    center_lon, center_lat = get_zone_centre(zone_insee)
    m_per_deg_lon = _M_PER_DEG_LAT * math.cos(math.radians(center_lat))

    dx_deg = (max_lon - min_lon) / (n - 1)
    dy_deg = (max_lat - min_lat) / (n - 1)
    dx_m = dx_deg * m_per_deg_lon
    dy_m = dy_deg * _M_PER_DEG_LAT
    cell_area_m2 = dx_m * dy_m

    return {
        "n": n, "min_lon": min_lon, "min_lat": min_lat,
        "dx_deg": dx_deg, "dy_deg": dy_deg, "dx_m": dx_m, "dy_m": dy_m,
        "cell_area_m2": cell_area_m2,
        "lon_centers": np.linspace(min_lon, max_lon, n),
        "lat_centers": np.linspace(min_lat, max_lat, n),
    }


def _latlon_to_cell(lon, lat, grid):
    i = int(round((lon - grid["min_lon"]) / grid["dx_deg"]))
    j = int(round((lat - grid["min_lat"]) / grid["dy_deg"]))
    n = grid["n"]
    return min(max(i, 0), n - 1), min(max(j, 0), n - 1)


def _car_source_grid(csv_path, grid):
    """Point sources: each sensor's average-daily Energy_MJ (from
    emissions_engine.compute_emissions, already computed) converted to a
    steady-state W/m² deposit on its nearest grid cell — same per-day
    averaging logic as spatial_heatmap_data.car_heatmap_points, since fetched
    history length differs between zones."""
    n = grid["n"]
    out = np.zeros((n, n))
    if not csv_path:
        return out, 0

    df = compute_emissions(csv_path)
    if df.empty:
        return out, 0

    n_days = df["date"].dt.floor("D").nunique() or 1
    avg_mj = df.groupby("sensor_id")["Energy_MJ"].sum() / n_days

    raw = pd.read_csv(csv_path)
    geo = raw["Geo Point"].astype(str).str.split(",", n=1, expand=True)
    raw["_lat"] = pd.to_numeric(geo[0], errors="coerce")
    raw["_lon"] = pd.to_numeric(geo[1], errors="coerce")
    coords = raw.dropna(subset=["_lat", "_lon"]).groupby(SENSOR_COL)[["_lat", "_lon"]].first()

    joined = avg_mj.to_frame("mj").join(coords, how="inner")
    for _, row in joined.iterrows():
        power_w = row["mj"] * 1_000_000 / 86400
        i, j = _latlon_to_cell(row["_lon"], row["_lat"], grid)
        out[j, i] += power_w / grid["cell_area_m2"]
    return out, len(joined)


def _bus_source_grid(zone_insee, grid):
    """Line sources: each bus line's daily_km x ENERGY_MJ_PER_KM['bus'] (from
    bus_emissions_engine.compute_bus_emissions_for_zone, already computed)
    converted to W and spread evenly across that line's GTFS shape points —
    same source data bus_emissions_engine already loads, read directly here
    (not through spatial_heatmap_data) to keep this engine self-contained."""
    n = grid["n"]
    out = np.zeros((n, n))
    result = compute_bus_emissions_for_zone(zone_insee)
    if result is None or result["total_km"] <= 0:
        return out, 0

    with open(_LINES_PATH, "r", encoding="utf-8") as f:
        lines_data = json.load(f)

    n_lines = 0
    for row in result["per_line"]:
        line = lines_data.get("bus", {}).get(row["code"])
        if not line:
            continue
        points = line.get("outbound") or line.get("inbound") or []
        if len(points) < 2:
            continue
        power_w = row["daily_km"] * ENERGY_MJ_PER_KM["bus"] * 1_000_000 / 86400
        share_w = power_w / len(points)
        for lon, lat in points:
            i, j = _latlon_to_cell(lon, lat, grid)
            out[j, i] += share_w / grid["cell_area_m2"]
        n_lines += 1
    return out, n_lines


def _wind_to_uv(speed_kmh, dir_deg):
    """wind_dir_deg (Open-Meteo / meteorological convention) is the direction
    the wind blows FROM, clockwise from north — so the velocity vector the air
    actually moves toward is the negative of that bearing's unit vector."""
    speed_ms = speed_kmh / 3.6
    rad = math.radians(dir_deg)
    u = -speed_ms * math.sin(rad)  # eastward (lon direction)
    v = -speed_ms * math.cos(rad)  # northward (lat direction)
    return u, v


def _all_hourly_wind(step=_ENSEMBLE_STEP):
    """Reads the single most recent weather_bordeaux_*.csv (one station for
    the whole métropole — see spec §1.2) in full (every hourly record
    collected so far, not just one day) and returns every `step`-th (u, v)
    pair in chronological order — a uniform subsample across the whole
    fetched history, so the ensemble spans real historical wind variability
    (different times of day AND different days), not one arbitrary day's
    diurnal cycle."""
    path = get_latest_file()
    if not path:
        return None
    df = pd.read_csv(path, parse_dates=["timestamp"]).sort_values("timestamp")
    if df.empty:
        return None
    sampled = df.iloc[::step]
    return [
        _wind_to_uv(r["wind_speed_kmh"], r["wind_dir_deg"])
        for _, r in sampled.iterrows()
    ], sampled["timestamp"].tolist()


def _laplacian(C, dx, dy):
    p = np.pad(C, 1, mode="edge")
    d2x = (p[1:-1, 2:] - 2 * p[1:-1, 1:-1] + p[1:-1, :-2]) / dx**2
    d2y = (p[2:, 1:-1] - 2 * p[1:-1, 1:-1] + p[:-2, 1:-1]) / dy**2
    return d2x + d2y


def _advection(C, u, v, dx, dy):
    """First-order upwind scheme; edge-padding approximates an open/outflow
    boundary (no reflection) rather than a rigorous radiative boundary — an
    adequate simplification since sources sit well inside the domain."""
    p = np.pad(C, 1, mode="edge")
    if u >= 0:
        dCdx = (p[1:-1, 1:-1] - p[1:-1, :-2]) / dx
    else:
        dCdx = (p[1:-1, 2:] - p[1:-1, 1:-1]) / dx
    if v >= 0:
        dCdy = (p[1:-1, 1:-1] - p[:-2, 1:-1]) / dy
    else:
        dCdy = (p[2:, 1:-1] - p[1:-1, 1:-1]) / dy
    return u * dCdx + v * dCdy


def _cfl_dt(dx, dy, D, u, v):
    """Combined von Neumann stability bound for the explicit FTCS-diffusion +
    upwind-advection scheme: the diffusion and advection Courant numbers must
    *sum* to <=1, not each independently stay under 1 — taking the min of two
    separate single-term bounds (an earlier, wrong version of this function)
    under-restricts dt by roughly 2x here and diverges within a few substeps."""
    denom = 2 * D * (1 / dx**2 + 1 / dy**2) + abs(u) / dx + abs(v) / dy
    return CFL_SAFETY_FACTOR / denom


def _run_to_quasi_steady(S, grid, u, v, spinup_hours=_SPINUP_HOURS):
    """One independent ensemble member: starts from C=0 and integrates with
    (u, v) held fixed for `spinup_hours` of simulated time (not wall-clock —
    same CFL-bounded substepping as before), then returns the grid at that
    point. Despite the name, this is deliberately an early NEAR-FIELD
    snapshot, not a run to true equilibrium — see the _SPINUP_HOURS comment
    and spec §2.5: this system's actual steady state is close to spatially
    uniform at this domain scale, so stopping early is what keeps local
    source structure visible. No memory carried in from any other member —
    each wind condition is independent, not a step in one real day's
    timeline."""
    dt = _cfl_dt(grid["dx_m"], grid["dy_m"], D_EDDY_M2S, u, v)
    total_seconds = spinup_hours * 3600
    n_sub = max(1, math.ceil(total_seconds / dt))
    dt_actual = total_seconds / n_sub

    C = np.zeros((grid["n"], grid["n"]))
    for _ in range(n_sub):
        lap = _laplacian(C, grid["dx_m"], grid["dy_m"])
        adv = _advection(C, u, v, grid["dx_m"], grid["dy_m"])
        C = C + dt_actual * (-adv + D_EDDY_M2S * lap - K_LOSS_S * C + S)
    return C


@st.cache_data(ttl=3600, show_spinner="Computing heat ensemble (this can take a while)...")
def compute_ensemble_heat(zone_insee, car_csv_path, include_car=True, include_bus=True):
    """Returns None if no wind data is available yet. Otherwise:
    {"lon_centers", "lat_centers", "mean_grid", "std_grid" ([n,n] arrays,
     W/m², relative intensity — see spec §2.3/§2.5), "n_samples",
     "n_car_sensors", "n_bus_lines"}.

    Ensemble over historical wind variability, not a time sequence: each of
    N sampled hourly wind records (see _all_hourly_wind) is run independently
    to an early near-field snapshot (_run_to_quasi_steady, spin-up
    deliberately short of true equilibrium — see spec §2.5), producing N
    independent 2D grids. mean_grid/std_grid are the cell-wise mean/std
    across those N grids — "expected traffic-heat pattern" and "how much it
    depends on wind conditions," not a diurnal trend (see spec §2.5 for why
    the earlier 24-hour continuous version was replaced, and why this is a
    snapshot rather than a run to full equilibrium)."""
    wind_result = _all_hourly_wind()
    if wind_result is None:
        return None
    hourly_uv, _ = wind_result

    grid = _build_grid(zone_insee)
    car_grid, n_car_sensors = _car_source_grid(car_csv_path, grid) if include_car else (np.zeros((grid["n"], grid["n"])), 0)
    bus_grid, n_bus_lines = _bus_source_grid(zone_insee, grid) if include_bus else (np.zeros((grid["n"], grid["n"])), 0)
    S = car_grid + bus_grid

    members = np.stack([_run_to_quasi_steady(S, grid, u, v) for u, v in hourly_uv])

    return {
        "lon_centers": grid["lon_centers"],
        "lat_centers": grid["lat_centers"],
        "mean_grid": members.mean(axis=0),
        "std_grid": members.std(axis=0),
        "n_samples": len(hourly_uv),
        "n_car_sensors": n_car_sensors,
        "n_bus_lines": n_bus_lines,
    }
