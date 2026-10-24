"""Glue used by the CLI, the web app and Temporal activities: readings -> features -> forecast -> decision."""
from __future__ import annotations

import datetime as dt
import threading
from functools import lru_cache
from importlib import resources
from pathlib import Path

from slabwatch.config import DATA, settings
from slabwatch.features import FEATURES, cut_features, feature_matrix

TRAIN_ASSET = "assets/train_rows.parquet"   # derived from PRECON (CC0); shipped so Render needs no download
FEATURES_PATH = DATA / "features.parquet"
_lock = threading.Lock()


def training_rows():
    import pandas as pd

    if FEATURES_PATH.exists():
        return pd.read_parquet(FEATURES_PATH)
    asset = resources.files("slabwatch").joinpath(TRAIN_ASSET)
    if asset.is_file():
        with resources.as_file(asset) as p:
            return pd.read_parquet(p)
    raise RuntimeError("No training rows. Run `python -m slabwatch fetch-data` then `build-features`.")


@lru_cache(maxsize=4)
def model(backend: str | None = None, max_rows: int = 3000):
    """Fit once per process (thread-safe). TabPFN context is capped at `max_rows` (sampled by house)."""
    from slabwatch.forecast import Forecaster

    s = settings()
    backend = backend or s.forecast_backend
    with _lock:
        df = training_rows()
        if (backend.startswith("tabpfn") or backend == "blend") and len(df) > max_rows:
            df = df.sample(max_rows, random_state=0)
        f = Forecaster(backend, token=s.tabpfn_token)
        if backend not in ("naive", "last_ratio"):
            f.fit(feature_matrix(df).values, df["ratio"].values)
        return f


def _parse_date(x) -> dt.date:
    return x if isinstance(x, dt.date) else dt.date.fromisoformat(str(x)[:10])


def forecast_cycle(cycle_start, start_reading: float, readings: list[dict], threshold: float | None = None,
                   cycle_days: int | None = None, meta: dict | None = None, prev_cycle_units: float | None = None,
                   backend: str | None = None, temps: dict | None = None) -> dict:
    """readings: [{"date": "YYYY-MM-DD", "reading_kwh": float}] (cumulative meter register).

    Day k of the cycle ends at cycle_start + k days, so a reading taken on cycle_start + k is day k.
    """
    from slabwatch.decide import decide

    s = settings()
    threshold = threshold if threshold is not None else s.slab_threshold
    cycle_days = cycle_days or s.cycle_days
    start = _parse_date(cycle_start)
    pts = sorted(((_parse_date(r["date"]) - start).days, float(r["reading_kwh"]) - start_reading)
                 for r in readings)
    pts = [p for p in pts if p[0] >= 1]
    if not pts:
        raise ValueError("need at least one reading taken on or after day 1 of the cycle")
    for (_, a), (_, b) in zip(pts, pts[1:]):
        if b < a:
            raise ValueError("meter readings must not go down")
    d = min(pts[-1][0], cycle_days)
    if pts[-1][1] < 0:
        raise ValueError("latest reading is below the cycle's starting reading")
    days = [start + dt.timedelta(days=i) for i in range(cycle_days)]
    if temps is None:
        from slabwatch.data.weather import temps_for

        temps = temps_for(days, s.lat, s.lon)
    tl = [temps.get(str(x)) for x in days]
    feats = cut_features(pts, d, start, tl[:d], tl[d:], cycle_days, meta or {},
                         prev_cycle_total=prev_cycle_units if prev_cycle_units else float("nan"))
    f = model(backend).forecast_one(feats, threshold, FEATURES, cycle_days)
    dec = decide(f.p10, f.p50, f.p90, f.p_cross, feats["units_so_far"], d, cycle_days, threshold,
                 s.penalty_months, backend=f.backend)
    return {"forecast": f.to_dict(), "decision": dec.to_dict(), "features": feats}


def notify(message: str, title: str = "Slabwatch", priority: str = "default") -> int:
    """Push via ntfy.sh (topic in NTFY_TOPIC). ntfy topics are public-by-name: use a long random one."""
    from slabwatch.net import post_text

    s = settings()
    topic = s.require("ntfy_topic", "NTFY_TOPIC", "push notifications")
    return post_text(f"{s.ntfy_server}/{topic}", message, {"Title": title, "Priority": priority})


def export_train_asset(df, path: Path | None = None, max_rows: int = 5000) -> Path:
    path = path or Path(str(resources.files("slabwatch").joinpath(TRAIN_ASSET)))
    path.parent.mkdir(parents=True, exist_ok=True)
    keep = [*FEATURES, "mean_temp_remaining_clim", "house", "cut", "ratio", "final_units"]
    out = df[keep].sample(min(max_rows, len(df)), random_state=0) if len(df) > max_rows else df[keep]
    out.to_parquet(path, index=False)
    return path
