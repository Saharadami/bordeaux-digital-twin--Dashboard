"""
Traffic forecasting engine — Bordeaux Urban Digital Twin
Rule-based, non-ML 7-day traffic forecast: ordinary least squares on a linear
trend + day-of-week dummy variables, fit on the zone's daily aggregate
(summed across all sensors) traffic counts.

Deliberately not ARIMA/statsmodels: the available history (26-40 days per
zone, ~4-6 occurrences of each weekday) is too short to defensibly select and
fit a seasonal ARIMA order. A day-of-week regression needs far fewer
observations to be meaningful and is easy to explain (one coefficient per
weekday + a trend slope). numpy only — no new dependency.
"""

import numpy as np
import pandas as pd

# ~90% CI. The band widens with sqrt(forecast step) — a simple, standard way
# to express growing uncertainty further into the forecast (mirrors random-walk
# error accumulation) without implying more precision than a 26-40 day history
# can support.
_Z_SCORE = 1.645

MIN_HISTORY_DAYS = 14


def forecast_traffic(csv_path: str, date_col: str, value_col: str, horizon_days: int = 7) -> pd.DataFrame:
    """Returns a tidy DataFrame [date, value, kind, lower, upper] — one row per
    day. `kind` is "actual" for history or "forecast" for the projected days.
    The last actual day is duplicated as the first forecast row so a line
    chart connects with no gap; `lower`/`upper` are NaN for actual rows.

    Raises ValueError if there are fewer than MIN_HISTORY_DAYS days of history
    (too little for a day-of-week fit to be meaningful).
    """
    df = pd.read_csv(csv_path)
    df[date_col] = pd.to_datetime(df[date_col], utc=True, errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=[date_col, value_col])
    df["_day"] = df[date_col].dt.floor("D")

    daily = df.groupby("_day")[value_col].sum().reset_index().sort_values("_day")
    daily.columns = ["date", "value"]

    n = len(daily)
    if n < MIN_HISTORY_DAYS:
        raise ValueError(
            f"Need at least {MIN_HISTORY_DAYS} days of history to fit a day-of-week "
            f"model, got {n}."
        )

    trend = np.arange(n, dtype=float)
    dow = daily["date"].dt.dayofweek.to_numpy()  # 0=Mon .. 6=Sun, Monday is the reference level
    X = np.column_stack([
        np.ones(n), trend,
        (dow == 1).astype(float), (dow == 2).astype(float), (dow == 3).astype(float),
        (dow == 4).astype(float), (dow == 5).astype(float), (dow == 6).astype(float),
    ])
    y = daily["value"].to_numpy(dtype=float)

    coeffs, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    fitted = X @ coeffs
    residuals = y - fitted
    dof = n - X.shape[1]
    sigma = float(np.std(residuals, ddof=dof)) if dof > 0 else float(np.std(residuals))

    last_date = daily["date"].max()
    future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=horizon_days, freq="D")
    future_trend = np.arange(n, n + horizon_days, dtype=float)
    future_dow = future_dates.dayofweek.to_numpy()
    Xf = np.column_stack([
        np.ones(horizon_days), future_trend,
        (future_dow == 1).astype(float), (future_dow == 2).astype(float), (future_dow == 3).astype(float),
        (future_dow == 4).astype(float), (future_dow == 5).astype(float), (future_dow == 6).astype(float),
    ])
    forecast_vals = np.clip(Xf @ coeffs, a_min=0, a_max=None)  # traffic counts can't be negative

    steps = np.arange(1, horizon_days + 1)
    band = _Z_SCORE * sigma * np.sqrt(steps)
    lower = np.clip(forecast_vals - band, a_min=0, a_max=None)
    upper = forecast_vals + band

    actual_part = pd.DataFrame({
        "date": daily["date"], "value": daily["value"], "kind": "actual",
        "lower": np.nan, "upper": np.nan,
    })
    bridge = pd.DataFrame({
        "date": [last_date], "value": [daily["value"].iloc[-1]], "kind": ["forecast"],
        "lower": [daily["value"].iloc[-1]], "upper": [daily["value"].iloc[-1]],
    })
    forecast_part = pd.DataFrame({
        "date": future_dates, "value": forecast_vals, "kind": "forecast",
        "lower": lower, "upper": upper,
    })

    out = pd.concat([actual_part, bridge, forecast_part], ignore_index=True)
    out.attrs["sigma"] = sigma
    out.attrs["n_history_days"] = n
    return out
