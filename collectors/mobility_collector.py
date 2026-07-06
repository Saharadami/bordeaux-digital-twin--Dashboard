"""
Mobility historical data collector — Bordeaux Urban Digital Twin
Source: Bordeaux Métropole Open Data (Opendatasoft Explore API v2.1)
Dataset: pc_velo_p — "Capteur de trafic vélo unifié - historique horaire"
          Hourly bike counter history, ~2 years rolling window, updated J+1.
No API key required.

Uses the /exports/csv endpoint (bulk download) instead of /records
(paginated search), because /records is capped at offset+limit <= 10000,
which this dataset exceeds within a few weeks (many sensors x hourly rows).

Dataset page: https://opendata.bordeaux-metropole.fr/explore/dataset/pc_velo_p/
"""

import os
import io
import requests
import pandas as pd
from datetime import datetime, timedelta

from zones import ZONES, DEFAULT_ZONE
from geo_utils import point_in_zone

DATASET_ID = "pc_velo_p"
SENSORS_DATASET_ID = "pc_captv_p"  # bike sensor locations (no `commune` field, geo-only)
RECORDS_URL = f"https://opendata.bordeaux-metropole.fr/api/explore/v2.1/catalog/datasets/{DATASET_ID}/records"
EXPORT_URL = f"https://opendata.bordeaux-metropole.fr/api/explore/v2.1/catalog/datasets/{DATASET_ID}/exports/csv"
SENSORS_SEARCH_URL = "https://opendata.bordeaux-metropole.fr/api/records/1.0/search/"

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "mobility")


def _sensor_idents_in_zone(zone_insee: str) -> list:
    """pc_captv_p only has coordinates (no `commune` field), so sensors are
    matched to the zone via point-in-polygon against its official boundary."""
    idents = []
    start = 0
    while True:
        r = requests.get(
            SENSORS_SEARCH_URL,
            params={"dataset": SENSORS_DATASET_ID, "rows": 100, "start": start},
            timeout=20,
        )
        r.raise_for_status()
        records = r.json().get("records", [])
        if not records:
            break
        for rec in records:
            f = rec["fields"]
            pt = f.get("geo_point_2d")
            if pt and point_in_zone(pt[1], pt[0], zone_insee):
                idents.append(f["ident"])
        start += 100
    return idents


def _guess_date_field(sample_record: dict):
    for key in sample_record.keys():
        lk = key.lower()
        if any(k in lk for k in ["date", "heure", "time"]):
            return key
    return None


def _probe_date_field():
    """Fetch a single record to learn the actual date/time column name."""
    resp = requests.get(RECORDS_URL, params={"limit": 1}, timeout=20)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        return None
    return _guess_date_field(results[0])


def collect(zone_insee: str = DEFAULT_ZONE, days_back: int = 90, save: bool = True) -> pd.DataFrame:
    """
    Fetch hourly bike traffic history for the last `days_back` days,
    scoped to sensors inside the given zone, from the pc_velo_p dataset
    via the bulk CSV export endpoint.
    """
    os.makedirs(DATA_DIR, exist_ok=True)

    idents = _sensor_idents_in_zone(zone_insee)
    if not idents:
        return pd.DataFrame()

    date_field = _probe_date_field()
    since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    ident_clause = "ident in (" + ",".join(f"'{i}'" for i in idents) + ")"

    params = {
        "lang": "fr",
        "timezone": "Europe/Paris",
        "use_labels": "true",
        "delimiter": ";",
    }
    where = ident_clause
    if date_field:
        where = f"{date_field} >= date'{since}' AND {ident_clause}"
    params["where"] = where

    try:
        resp = requests.get(EXPORT_URL, params=params, timeout=60)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if date_field:
            # date field guess may be wrong for the export endpoint — retry with zone filter only
            params["where"] = ident_clause
            resp = requests.get(EXPORT_URL, params=params, timeout=60)
            resp.raise_for_status()
        else:
            raise RuntimeError(
                f"Bordeaux Métropole export API error ({e}). "
                f"Check https://opendata.bordeaux-metropole.fr/explore/dataset/{DATASET_ID}/"
            )

    df = pd.read_csv(io.StringIO(resp.text), sep=";")

    if save and not df.empty:
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
        zone_slug = ZONES[zone_insee]["name"].lower()
        path = os.path.join(DATA_DIR, f"bike_traffic_{zone_slug}_{stamp}.csv")
        df.to_csv(path, index=False)

    return df


if __name__ == "__main__":
    df = collect(days_back=30, save=True)
    print(f"Fetched {len(df)} records")
    if not df.empty:
        print(df.columns.tolist())
        print(df.head())