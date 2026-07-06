"""
Emissions engine — Bordeaux Urban Digital Twin
Reads an existing car-traffic CSV (data/traffic/car_traffic_<zone>_*.csv, already
produced by collectors/traffic_collector.py) and estimates CO2/NOx/PM per
sensor/day using emission_factors.estimate_emissions(). No new data collection —
pandas only, per emission_engine_spec.md §5.
"""

import pandas as pd

from emissions.emission_factors import estimate_emissions

DATE_COL = "Date de comptage"
SENSOR_COL = "ident"
VALUE_COL = "comptage_5m"


def compute_emissions(csv_path: str) -> pd.DataFrame:
    """Returns a DataFrame with columns [sensor_id, date, vehicle_count, CO2_g,
    NOx_g, PM_g] — one row per (sensor, day), same granularity as the source CSV."""
    df = pd.read_csv(csv_path)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL], utc=True, errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=[DATE_COL, SENSOR_COL, VALUE_COL])

    emissions = df[VALUE_COL].apply(estimate_emissions).apply(pd.Series).add_suffix("_g")

    out = pd.DataFrame({
        "sensor_id": df[SENSOR_COL].values,
        "date": df[DATE_COL].values,
        "vehicle_count": df[VALUE_COL].values,
    })
    return pd.concat([out, emissions.reset_index(drop=True)], axis=1)
