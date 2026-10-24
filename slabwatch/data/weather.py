"""Open-Meteo daily temperatures (free, no key), cached on disk as JSON.

- archive():     historical daily mean/max (ERA5-based archive API), e.g. PRECON's 2018-06..2019-05
- forecast():    next <=16 days from the forecast API (checked live 2026-10-24)
- climatology(): mean temperature by day-of-year over past years (used when no forecast exists)
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
from pathlib import Path

from slabwatch.config import CACHE
from slabwatch.net import get_json

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TZ = "Asia/Karachi"
DAILY_VARS = "temperature_2m_mean,temperature_2m_max"


def _cached(name: str, params: dict, url: str, max_age_s: float | None) -> dict:
    key = hashlib.sha1(json.dumps([url, params], sort_keys=True).encode()).hexdigest()[:16]
    path = Path(CACHE) / "weather" / f"{name}-{key}.json"
    if path.exists() and (max_age_s is None or time.time() - path.stat().st_mtime < max_age_s):
        return json.loads(path.read_text())
    data = get_json(url, params, timeout=60)
    if "daily" not in data:
        raise RuntimeError(f"Open-Meteo returned no daily data: {str(data)[:200]}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data


def _to_map(data: dict) -> dict[str, dict[str, float | None]]:
    d = data["daily"]
    return {t: {"tmean": m, "tmax": x}
            for t, m, x in zip(d["time"], d["temperature_2m_mean"], d["temperature_2m_max"])}


def archive(start: str | dt.date, end: str | dt.date, lat: float, lon: float) -> dict[str, dict]:
    """{ 'YYYY-MM-DD': {'tmean': C, 'tmax': C} }. Past data never changes, so the cache never expires."""
    p = {"latitude": lat, "longitude": lon, "start_date": str(start), "end_date": str(end),
         "daily": DAILY_VARS, "timezone": TZ}
    return _to_map(_cached("archive", p, ARCHIVE_URL, None))


def forecast(lat: float, lon: float, days: int = 16, past_days: int = 14) -> dict[str, dict]:
    """Next `days` (max 16) days plus the last `past_days` (fills the archive's ~5-day lag). Cached 3 h."""
    p = {"latitude": lat, "longitude": lon, "daily": DAILY_VARS, "timezone": TZ,
         "forecast_days": min(max(days, 1), 16), "past_days": past_days}
    return _to_map(_cached("forecast", p, FORECAST_URL, 3 * 3600))


def climatology(lat: float, lon: float, years: tuple[int, int] = (2008, 2017)) -> dict[int, float]:
    """Day-of-year (1..366) -> mean daily temperature across `years`, smoothed with a 15-day window.
    Default years end before PRECON (2018-19) so the backtest climatology never sees the test period."""
    a = archive(f"{years[0]}-01-01", f"{years[1]}-12-31", lat, lon)
    sums: dict[int, list[float]] = {}
    for day, v in a.items():
        if v["tmean"] is not None:
            sums.setdefault(dt.date.fromisoformat(day).timetuple().tm_yday, []).append(v["tmean"])
    raw = {k: sum(v) / len(v) for k, v in sums.items()}
    out = {}
    for k in range(1, 367):
        win = [raw[((k - 1 + o) % 366) + 1] for o in range(-7, 8) if ((k - 1 + o) % 366) + 1 in raw]
        out[k] = sum(win) / len(win) if win else float("nan")
    return out


def temps_for(dates: list[dt.date], lat: float, lon: float) -> dict[str, float | None]:
    """Best available mean temp for each date: archive for the past, forecast for the next 16 days,
    climatology beyond that. Returns {date: tmean}."""
    today = dt.date.today()
    out: dict[str, float | None] = {}
    past = [d for d in dates if d < today - dt.timedelta(days=5)]  # archive lags ~5 days
    if past:
        a = archive(min(past), max(past), lat, lon)
        out.update({k: v["tmean"] for k, v in a.items()})
    rest = [d for d in dates if str(d) not in out]
    if rest:
        f = forecast(lat, lon)
        out.update({k: v["tmean"] for k, v in f.items() if k not in out})
    missing = [d for d in dates if out.get(str(d)) is None]
    if missing:
        clim = climatology(lat, lon)
        for d in missing:
            out[str(d)] = clim[d.timetuple().tm_yday]
    return {str(d): out[str(d)] for d in dates}
