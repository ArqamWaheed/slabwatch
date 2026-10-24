"""Training rows: (house, 30-day cycle window, cut day) -> features known at the cut + scale-free target.

Target  ratio = final_units / (rate_so_far * cycle_days)    (1.0 == "just multiply it out")

Leakage rule: `cut_features()` only ever receives the cumulative-units curve up to the cut day,
temperatures, and static metadata. Units after the cut never enter it (tests/test_features.py).

Weather note: in the backtest, `mean_temp_remaining` uses the *actual* temperature of the remaining
days as a stand-in for a weather forecast. That is OPTIMISTIC (a real forecast has error, and
Open-Meteo only reaches 16 days ahead). The `clim` variant replaces it with day-of-year
climatology from 2008-2017, which is the pessimistic bound (no forecast skill at all).
"""
from __future__ import annotations

import datetime as dt
import math
from collections.abc import Sequence

CUT_DAYS = (5, 7, 10, 14, 18, 21, 25)
CYCLE_DAYS = 30
WINDOW_STEP = 15
MIN_DAILY_KWH = 0.5
META_COLS = ("n_acs", "area_sqft", "people")
FEATURES = (
    "days_elapsed", "days_left", "units_so_far", "rate_so_far",
    "rate_last_3_days", "rate_last_7_days", "recent_over_rate",
    "mean_temp_so_far", "mean_temp_remaining", "temp_delta", "month",
    *META_COLS, "last_cycle_ratio", "prev_total_over_naive",
)


def interp_cum(points: Sequence[tuple[float, float]], day: float) -> float:
    """Cumulative units at `day` by linear interpolation of (day, cumulative) points (sorted, incl. (0,0))."""
    pts = sorted(points)
    if day <= pts[0][0]:
        return pts[0][1]
    for (d0, c0), (d1, c1) in zip(pts, pts[1:]):
        if day <= d1:
            return c0 + (c1 - c0) * (day - d0) / (d1 - d0) if d1 > d0 else c1
    return pts[-1][1]


def _mean(xs: Sequence[float | None]) -> float:
    v = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return sum(v) / len(v) if v else float("nan")


def cut_features(
    cum_points: Sequence[tuple[float, float]],
    days_elapsed: int,
    cycle_start: dt.date,
    temps_so_far: Sequence[float | None],
    temps_remaining: Sequence[float | None],
    cycle_days: int = CYCLE_DAYS,
    meta: dict | None = None,
    last_cycle_ratio: float = float("nan"),
    prev_cycle_total: float = float("nan"),
) -> dict:
    """Features for one cut. `cum_points` = (day, cumulative units) with day <= days_elapsed.

    Training passes one point per day; live use passes the meter readings (interpolated the same way).
    """
    d = days_elapsed
    pts = [(0.0, 0.0), *[(float(a), float(b)) for a, b in cum_points if a <= d]]
    if max(p[0] for p in pts) < d:
        raise ValueError("cum_points must include the cut day itself")
    so_far = interp_cum(pts, d)
    rate = so_far / d
    r3 = (so_far - interp_cum(pts, max(d - 3, 0))) / min(3, d)
    r7 = (so_far - interp_cum(pts, max(d - 7, 0))) / min(7, d)
    t_so, t_rem = _mean(temps_so_far), _mean(temps_remaining)
    cut_date = cycle_start + dt.timedelta(days=d)
    meta = meta or {}
    naive = rate * cycle_days
    return {
        "days_elapsed": d,
        "days_left": cycle_days - d,
        "units_so_far": so_far,
        "rate_so_far": rate,
        "rate_last_3_days": r3,
        "rate_last_7_days": r7,
        "recent_over_rate": r7 / rate if rate > 0 else float("nan"),
        "mean_temp_so_far": t_so,
        "mean_temp_remaining": t_rem,
        "temp_delta": t_rem - t_so,
        "month": cut_date.month,
        **{k: float(meta.get(k, float("nan"))) for k in META_COLS},
        "last_cycle_ratio": last_cycle_ratio,
        "prev_total_over_naive": prev_cycle_total / naive if naive > 0 else float("nan"),
    }


def build_rows(daily, meta, temps: dict[str, float], clim: dict[int, float] | None = None,
               cuts: Sequence[int] = CUT_DAYS, cycle_days: int = CYCLE_DAYS, step: int = WINDOW_STEP,
               min_coverage: float = 0.9, min_daily_kwh: float = MIN_DAILY_KWH):
    """daily: DataFrame(house, date, kwh, coverage). Returns a DataFrame of training rows.

    A window is used only if all `cycle_days` days exist with coverage >= min_coverage and
    kwh >= min_daily_kwh (PRECON has multi-week runs of ~0 kWh in houses 2, 3, 10: logger dropouts or
    a vacant house; a running fridge alone is > 0.5 kWh/day, so those days are treated as missing).
    Columns: FEATURES + mean_temp_remaining_clim + house, cycle_start, cut, final_units, naive_units, ratio.
    """
    import pandas as pd

    meta_by_house = {int(r["house"]): r for r in meta.to_dict("records")} if meta is not None else {}
    rows = []
    for house, g in daily.groupby("house"):
        g = g.sort_values("date")
        ok = {pd.Timestamp(r.date).date(): r.kwh for r in g.itertuples() if r.coverage >= min_coverage and r.kwh >= min_daily_kwh}
        if not ok:
            continue
        first, last = min(ok), max(ok)
        starts = []
        s = first
        while s + dt.timedelta(days=cycle_days - 1) <= last:
            days = [s + dt.timedelta(days=i) for i in range(cycle_days)]
            if all(x in ok for x in days):
                starts.append(s)
            s += dt.timedelta(days=step)
        m = meta_by_house.get(int(house), {})
        for s in starts:
            days = [s + dt.timedelta(days=i) for i in range(cycle_days)]
            kwh = [ok[x] for x in days]
            cum = [sum(kwh[: i + 1]) for i in range(cycle_days)]
            final = cum[-1]
            tday = [temps.get(str(x)) for x in days]
            prev_s = s - dt.timedelta(days=cycle_days)
            prev_days = [prev_s + dt.timedelta(days=i) for i in range(cycle_days)]
            prev_ok = all(x in ok for x in prev_days)
            prev_kwh = [ok[x] for x in prev_days] if prev_ok else None
            prev_total = sum(prev_kwh) if prev_ok else float("nan")
            for d in cuts:
                pts = [(i + 1, cum[i]) for i in range(d)]  # end of day i+1 -> cumulative
                last_ratio = float("nan")
                if prev_ok:
                    prate = sum(prev_kwh[:d]) / d
                    last_ratio = prev_total / (prate * cycle_days) if prate > 0 else float("nan")
                f = cut_features(pts, d, s, tday[:d], tday[d:], cycle_days, m, last_ratio, prev_total)
                if clim is not None:
                    f["mean_temp_remaining_clim"] = _mean([clim[x.timetuple().tm_yday] for x in days[d:]])
                naive = f["rate_so_far"] * cycle_days
                if naive <= 0:
                    continue
                rows.append({**f, "house": int(house), "cycle_start": s, "cut": d,
                             "final_units": final, "naive_units": naive, "ratio": final / naive})
    return pd.DataFrame(rows)


def feature_matrix(df, weather: str = "actual"):
    """X for a model. weather='clim' swaps in climatology for the remaining-days temperature."""
    X = df[list(FEATURES)].copy()
    if weather == "clim":
        X["mean_temp_remaining"] = df["mean_temp_remaining_clim"]
        X["temp_delta"] = X["mean_temp_remaining"] - X["mean_temp_so_far"]
    return X.astype(float)
