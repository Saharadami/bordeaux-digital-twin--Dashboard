"""
Emissions engine — Bordeaux Urban Digital Twin
Reads an existing car-traffic CSV (data/traffic/car_traffic_<zone>_*.csv, already
produced by collectors/traffic_collector.py) and estimates CO2/NOx/PM per
sensor/day using emission_factors.estimate_emissions(). No new data collection —
pandas only, per emission_engine_spec.md §5.
"""

import pandas as pd

from emissions.emission_factors import estimate_emissions, ENERGY_MJ_PER_KM, UNIT_DISTANCE_KM

DATE_COL = "Date de comptage"
SENSOR_COL = "ident"
VALUE_COL = "comptage_5m"

# A sensor/day is a statistical outlier if its count is more than this many
# times the median count across all sensors on that same day. Investigated one
# concrete case (Bordeaux, sensor Z201CT2): ~461K/day vs a ~3K/day zone median
# — confirmed via a direct re-fetch from the source API that the raw value
# really is what TBM's dataset reports (not a bug in our own collector), so
# this is a source data-quality issue, not project-specific. General (day- and
# zone-agnostic) rather than hardcoded to that one sensor ID.
OUTLIER_MEDIAN_MULTIPLIER = 10


def compute_emissions(csv_path: str) -> pd.DataFrame:
    """Returns a DataFrame with columns [sensor_id, date, vehicle_count, CO2_g,
    NOx_g, PM_g, Energy_MJ] — one row per (sensor, day), same granularity as
    the source CSV.

    Rows flagged as statistical outliers (see OUTLIER_MEDIAN_MULTIPLIER) are
    excluded from the result so a single malfunctioning sensor can't dominate
    a zone's emission totals. The list of excluded sensor IDs is attached to
    the returned DataFrame as `.attrs["excluded_sensor_ids"]`.
    """
    df = pd.read_csv(csv_path)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL], utc=True, errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=[DATE_COL, SENSOR_COL, VALUE_COL])

    daily_median = df.groupby(DATE_COL)[VALUE_COL].transform("median")
    is_outlier = (daily_median > 0) & (df[VALUE_COL] > OUTLIER_MEDIAN_MULTIPLIER * daily_median)
    excluded_sensor_ids = sorted(df.loc[is_outlier, SENSOR_COL].unique().tolist())
    df = df.loc[~is_outlier]

    emissions = df[VALUE_COL].apply(estimate_emissions).apply(pd.Series).add_suffix("_g")

    out = pd.DataFrame({
        "sensor_id": df[SENSOR_COL].values,
        "date": df[DATE_COL].values,
        "vehicle_count": df[VALUE_COL].values,
    })
    out = pd.concat([out, emissions.reset_index(drop=True)], axis=1)
    out["Energy_MJ"] = df[VALUE_COL].values * ENERGY_MJ_PER_KM["car"] * UNIT_DISTANCE_KM
    out.attrs["excluded_sensor_ids"] = excluded_sensor_ids
    return out
