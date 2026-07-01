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

DATASET_ID = "pc_velo_p"
RECORDS_URL = f"https://opendata.bordeaux-metropole.fr/api/explore/v2.1/catalog/datasets/{DATASET_ID}/records"
EXPORT_URL = f"https://opendata.bordeaux-metropole.fr/api/explore/v2.1/catalog/datasets/{DATASET_ID}/exports/csv"

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "mobility")


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


def collect(days_back: int = 90, save: bool = True) -> pd.DataFrame:
    """
    Fetch hourly bike traffic history for the last `days_back` days
    from the pc_velo_p dataset via the bulk CSV export endpoint.
    """
    os.makedirs(DATA_DIR, exist_ok=True)

    date_field = _probe_date_field()
    since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    params = {
        "lang": "fr",
        "timezone": "Europe/Paris",
        "use_labels": "true",
        "delimiter": ";",
    }
    if date_field:
        params["where"] = f"{date_field} >= date'{since}'"

    try:
        resp = requests.get(EXPORT_URL, params=params, timeout=60)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if date_field:
            # date field guess may be wrong for the export endpoint — retry with no filter
            params.pop("where", None)
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
        path = os.path.join(DATA_DIR, f"bike_traffic_{stamp}.csv")
        df.to_csv(path, index=False)

    return df


if __name__ == "__main__":
    df = collect(days_back=30, save=True)
    print(f"Fetched {len(df)} records")
    if not df.empty:
        print(df.columns.tolist())
        print(df.head())