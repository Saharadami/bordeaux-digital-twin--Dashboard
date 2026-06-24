"""
Weather Collector — Bordeaux Urban Digital Twin
Source: Open-Meteo API (no API key required)
Docs:   https://open-meteo.com/en/docs/meteofrance-api
"""

import requests
import pandas as pd
import os
from datetime import datetime, timedelta


# ── Configuration ─────────────────────────────────────────────────────
LATITUDE  = 44.8378
LONGITUDE = -0.5792
CITY      = "Bordeaux"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "weather")
BASE_URL   = "https://api.open-meteo.com/v1/meteofrance"

HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "shortwave_radiation",
    "weather_code",
]


# ── Helper functions ───────────────────────────────────────────────────

def get_date_range(days_back: int = 30):
    """
    تاریخ شروع و پایان را برمی‌گرداند.
    days_back: چند روز به عقب برگردیم
    """
    end_date   = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    return (
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d")
    )


def fetch_weather(start_date: str, end_date: str) -> dict:
    """
    داده آب‌وهوا را از Open-Meteo API می‌گیرد.
    
    requests.get() یک HTTP GET request ارسال می‌کند.
    params= پارامترها را به URL اضافه می‌کند:
    ?latitude=44.84&longitude=-0.58&hourly=temperature_2m,...
    
    response.raise_for_status() اگر status code != 200 باشد خطا می‌دهد.
    response.json() جواب JSON را به dictionary تبدیل می‌کند.
    """
    params = {
        "latitude":   LATITUDE,
        "longitude":  LONGITUDE,
        "hourly":     ",".join(HOURLY_VARIABLES),
        "start_date": start_date,
        "end_date":   end_date,
        "timezone":   "Europe/Paris",
    }

    print(f"Fetching weather: {start_date} to {end_date}")
    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    print(f"Received {len(data['hourly']['time'])} hourly records")
    return data


def parse_to_dataframe(raw_data: dict) -> pd.DataFrame:
    """
    داده‌های خام API را به DataFrame تبدیل می‌کند.
    
    ساختار جواب API:
    {
      "hourly": {
        "time": ["2026-06-01T00:00", ...],
        "temperature_2m": [18.5, ...],
        ...
      }
    }
    
    pd.DataFrame(dict) → هر کلید = یک ستون، هر مقدار = داده‌های آن ستون
    pd.to_datetime() → تبدیل string به نوع datetime برای فیلتر و مرتب‌سازی
    """
    hourly = raw_data["hourly"]

    df = pd.DataFrame({
        "timestamp":        hourly["time"],
        "temperature_c":    hourly["temperature_2m"],
        "humidity_pct":     hourly["relative_humidity_2m"],
        "precipitation_mm": hourly["precipitation"],
        "wind_speed_kmh":   hourly["wind_speed_10m"],
        "wind_dir_deg":     hourly["wind_direction_10m"],
        "solar_rad_wm2":    hourly["shortwave_radiation"],
        "weather_code":     hourly["weather_code"],
    })

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["city"]      = CITY
    df["latitude"]  = LATITUDE
    df["longitude"] = LONGITUDE
    df["source"]    = "open-meteo"

    return df


def save_to_csv(df: pd.DataFrame, filename: str = None) -> str:
    """
    DataFrame را به فایل CSV ذخیره می‌کند.
    
    os.makedirs(exist_ok=True) → پوشه را می‌سازد اگر وجود نداشته باشد
    df.to_csv(index=False) → بدون ستون شماره ردیف ذخیره می‌کند
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if filename is None:
        today    = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"weather_bordeaux_{today}.csv"

    filepath = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(filepath, index=False, encoding="utf-8")
    print(f"Saved {len(df)} rows → {filepath}")
    return filepath


def get_latest_file() -> str | None:
    """
    آخرین فایل CSV ذخیره شده را پیدا می‌کند.
    برای dashboard — به جای fetch مجدد، آخرین داده را بخوان.
    
    os.listdir() → لیست همه فایل‌های پوشه
    max(key=os.path.getmtime) → جدیدترین فایل بر اساس تاریخ تغییر
    """
    if not os.path.exists(OUTPUT_DIR):
        return None

    files = [
        os.path.join(OUTPUT_DIR, f)
        for f in os.listdir(OUTPUT_DIR)
        if f.endswith(".csv")
    ]

    if not files:
        return None

    return max(files, key=os.path.getmtime)


def load_latest() -> pd.DataFrame | None:
    """
    آخرین داده ذخیره شده را load می‌کند.
    parse_dates=["timestamp"] → ستون timestamp را به datetime تبدیل می‌کند
    """
    filepath = get_latest_file()
    if filepath is None:
        return None

    df = pd.read_csv(filepath, parse_dates=["timestamp"])
    print(f"Loaded {len(df)} rows from {filepath}")
    return df


# ── Main function ──────────────────────────────────────────────────────

def collect(days_back: int = 30, save: bool = True) -> pd.DataFrame:
    """
    تابع اصلی — همه مراحل را با هم اجرا می‌کند.
    
    استفاده از dashboard:
        from collectors import weather_collector
        df = weather_collector.collect(days_back=7)
    
    استفاده مستقیم از terminal:
        python collectors/weather_collector.py
    
    مراحل:
        1. get_date_range()     → محاسبه بازه تاریخ
        2. fetch_weather()      → دریافت از API
        3. parse_to_dataframe() → تبدیل به DataFrame
        4. save_to_csv()        → ذخیره CSV
    """
    start_date, end_date = get_date_range(days_back)
    raw_data = fetch_weather(start_date, end_date)
    df = parse_to_dataframe(raw_data)
    if save:
        save_to_csv(df)
    return df


# ── Run directly ───────────────────────────────────────────────────────
# این بلوک فقط وقتی فایل مستقیم اجرا می‌شود فعال است:
#   python collectors/weather_collector.py
# وقتی import می‌شود این بلوک اجرا نمی‌شود.

if __name__ == "__main__":
    print("=" * 50)
    print("Bordeaux Weather Collector")
    print("=" * 50)

    df = collect(days_back=30)

    print("\nSample (first 3 rows):")
    print(df[["timestamp","temperature_c","precipitation_mm","wind_speed_kmh"]].head(3).to_string())

    print(f"\nSummary:")
    print(f"  Period:     {df['timestamp'].min()} → {df['timestamp'].max()}")
    print(f"  Records:    {len(df)}")
    print(f"  Avg temp:   {df['temperature_c'].mean():.1f}°C")
    print(f"  Total rain: {df['precipitation_mm'].sum():.1f}mm")
    print(f"  Avg wind:   {df['wind_speed_kmh'].mean():.1f}km/h")
