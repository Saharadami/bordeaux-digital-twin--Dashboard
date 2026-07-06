"""
Car traffic collector — Bordeaux Urban Digital Twin
Source: Bordeaux Métropole Open Data (Opendatasoft)
  - pc_capte_p            : live 5-minute traffic counts per sensor (has a
                             direct `commune` field — used to find which
                             sensors belong to a zone)
  - pc_capte_p_histo_jour : daily historical counts per sensor, joined back
                             to the zone via the sensor `ident`s found above
Scoped to a zone from zones.py (default: Talence). Add more communes to
zones.py and this collector picks them up automatically.
"""

import os
import io
import requests
import pandas as pd
from datetime import datetime, timedelta

from zones import ZONES, DEFAULT_ZONE

RECORDS_URL = "https://opendata.bordeaux-metropole.fr/api/records/1.0/search/"
EXPORT_URL_HISTO = (
    "https://opendata.bordeaux-metropole.fr/api/explore/v2.1/catalog/"
    "datasets/pc_capte_p_histo_jour/exports/csv"
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "traffic")


def fetch_live(zone_insee: str = DEFAULT_ZONE) -> pd.DataFrame:
    """Current 5-minute traffic counts for every sensor in the zone."""
    zone_name = ZONES[zone_insee]["name"]
    resp = requests.get(
        RECORDS_URL,
        params={"dataset": "pc_capte_p", "refine.commune": zone_name, "rows": 500},
        timeout=20,
    )
    resp.raise_for_status()
    records = resp.json().get("records", [])
    return pd.DataFrame([r["fields"] for r in records])


def collect(zone_insee: str = DEFAULT_ZONE, days_back: int = 90, save: bool = True) -> pd.DataFrame:
    """Daily historical traffic counts for every sensor in the zone, last `days_back` days."""
    os.makedirs(DATA_DIR, exist_ok=True)

    live = fetch_live(zone_insee)
    if live.empty or "ident" not in live.columns:
        return pd.DataFrame()
    idents = sorted(live["ident"].dropna().unique().tolist())

    since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    ident_list = ",".join(f"'{i}'" for i in idents)
    where = f"time >= date'{since}' AND ident in ({ident_list})"

    resp = requests.get(
        EXPORT_URL_HISTO,
        params={
            "lang": "fr", "timezone": "Europe/Paris", "use_labels": "true",
            "delimiter": ";", "where": where,
        },
        timeout=60,
    )
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), sep=";")

    if save and not df.empty:
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
        zone_slug = ZONES[zone_insee]["name"].lower()
        path = os.path.join(DATA_DIR, f"car_traffic_{zone_slug}_{stamp}.csv")
        df.to_csv(path, index=False)

    return df


if __name__ == "__main__":
    live = fetch_live()
    print(f"Live sensors in zone: {len(live)}")

    df = collect(days_back=90, save=True)
    print(f"Fetched {len(df)} historical daily records")
    if not df.empty:
        print(df.columns.tolist())
        print(df.head())
