"""Backtest: GroupKFold by house (no house is ever in its own training set).

Metrics per model and cut day:
  MAPE        |P50 - final| / final, mean over rows
  coverage    share of rows with P10 <= final <= P90 (nominal 80%)
  Brier       mean (P(cross) - over)^2, over = final > T
  precision / recall of the call "P(cross) >= 0.5"
Synthetic threshold: PRECON homes use far more than 200 units, so T for each house is the MEDIAN of
that house's own 30-day totals. About half of each house's cycles are then "over", which makes the
cliff call non-trivial. T only defines the event being scored; it is never a model input.
"""
from __future__ import annotations

import datetime as dt
import json
import platform
import time

import numpy as np

from slabwatch.config import DATA, RESULTS, ROOT, settings
from slabwatch.features import feature_matrix
from slabwatch.forecast import QUANTILES, Forecaster, p_cross

TABPFN = ("tabpfn_local", "tabpfn_api")


def _available(m: str, token: str) -> str | None:
    if m == "tabpfn_local":
        try:
            import tabpfn  # noqa: F401
        except ImportError:
            return "tabpfn not installed (pip install -e .[local])"
    if m == "tabpfn_api" and not token:
        return "TABPFN_TOKEN not set"
    return None


def _metrics(final, p10, p50, p90, pc, over) -> dict:
    call = pc >= 0.5
    tp = int((call & over).sum())
    return {
        "n": int(len(final)),
        "mape": float(np.mean(np.abs(p50 - final) / final)),
        "coverage_80": float(np.mean((final >= p10) & (final <= p90))),
        "brier": float(np.mean((pc - over.astype(float)) ** 2)),
        "precision": float(tp / call.sum()) if call.sum() else None,
        "recall": float(tp / over.sum()) if over.sum() else None,
        "base_rate": float(over.mean()),
    }


def run_backtest(models: list[str], weather: str = "actual", folds: int = 5, sample: int = 0,
                 seed: int = 0, write: bool = True) -> dict:
    import pandas as pd
    from sklearn.model_selection import GroupKFold

    s = settings()
    path = DATA / "features.parquet"
    if not path.exists():
        raise RuntimeError("data/features.parquet missing: run fetch-data then build-features")
    df = pd.read_parquet(path).reset_index(drop=True)
    X = feature_matrix(df, weather).values
    y = df["ratio"].values
    houses = df["house"].values
    n_houses = len(np.unique(houses))
    folds = min(folds, n_houses)

    # synthetic per-house threshold = median 30-day total of that house's windows
    totals = df.drop_duplicates(["house", "cycle_start"]).groupby("house")["final_units"].median()
    T = df["house"].map(totals).values
    final = df["final_units"].values
    over = final > T
    size = df.drop_duplicates(["house", "cycle_start"]).groupby("house")["final_units"].median()
    terc = pd.qcut(size, 3, labels=["small", "mid", "large"]) if n_houses >= 3 else None

    skipped, preds, timings = {}, {}, {}
    for m in models:
        why = _available(m, s.tabpfn_token)
        if why:
            skipped[m] = why
            continue
        out = np.zeros((len(df), len(QUANTILES)))
        t0 = time.time()
        for tr, te in GroupKFold(n_splits=folds).split(X, y, houses):
            if m in TABPFN and sample and len(tr) > sample:
                tr = np.random.default_rng(seed).choice(tr, sample, replace=False)
            f = Forecaster(m, token=s.tabpfn_token, seed=seed)
            if m not in ("naive", "last_ratio"):
                f.fit(X[tr], y[tr])
            out[te] = f.predict_ratio_quantiles(X[te], last_ratio=df["last_cycle_ratio"].values[te])
        timings[m] = round(time.time() - t0, 2)
        units = np.maximum(out * df["naive_units"].values[:, None], df["units_so_far"].values[:, None])
        preds[m] = units

    lv = list(QUANTILES)
    i10, i50, i90 = lv.index(0.1), lv.index(0.5), lv.index(0.9)
    results: dict = {"by_cut": {}, "overall": {}, "by_size": {}}
    for m, u in preds.items():
        pc = np.array([p_cross(T[i], lv, u[i]) for i in range(len(u))])
        args = (u[:, i10], u[:, i50], u[:, i90], pc)
        results["overall"][m] = _metrics(final, *args, over)
        results["by_cut"][m] = {int(c): _metrics(final[idx], *(a[idx] for a in args), over[idx])
                                for c in sorted(df["cut"].unique()) for idx in [df["cut"].values == c]}
        if terc is not None:
            tmap = df["house"].map(terc).astype(str).values
            results["by_size"][m] = {t: _metrics(final[idx], *(a[idx] for a in args), over[idx])
                                     for t in ("small", "mid", "large") for idx in [tmap == t]}

    run = {
        "date_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "weather": weather, "folds": folds, "sample": sample, "seed": seed,
        "rows": int(len(df)), "houses": int(n_houses),
        "windows": int(df.drop_duplicates(["house", "cycle_start"]).shape[0]),
        "cuts": sorted(int(c) for c in df["cut"].unique()),
        "threshold_rule": "per-house median 30-day total (synthetic)",
        "skipped": skipped, "seconds": timings, "python": platform.python_version(), **results,
    }
    if write:
        RESULTS.mkdir(exist_ok=True)
        p = RESULTS / f"backtest-{weather}-{dt.datetime.now():%Y%m%d-%H%M%S}.json"
        p.write_text(json.dumps(run, indent=2))
        (RESULTS / f"backtest-{weather}-latest.json").write_text(json.dumps(run, indent=2))
        write_results_md()
        run["written"] = str(p)
    return run


def _fmt(x, pct=True) -> str:
    if x is None:
        return "-"
    return f"{x * 100:.1f}%" if pct else f"{x:.3f}"


def write_results_md() -> None:
    """docs/RESULTS.md from the latest saved runs (actual-weather and climatology)."""
    lines = ["# Backtest results", "",
             "Generated by `python -m slabwatch backtest` (slabwatch/evaluate.py) from `results/backtest-*-latest.json`.",
             "Do not edit by hand. GroupKFold by house; nothing from a test house is in its training fold.", ""]
    for w in ("actual", "clim"):
        p = RESULTS / f"backtest-{w}-latest.json"
        if not p.exists():
            continue
        r = json.loads(p.read_text())
        label = ("actual future temperatures as a stand-in for a forecast (OPTIMISTIC)" if w == "actual"
                 else "day-of-year climatology 2008-2017 for the remaining days (no forecast skill)")
        lines += [f"## Weather: {w}", "",
                  f"Run {r['date_utc']} · {r['houses']} houses · {r['windows']} windows · {r['rows']} rows · "
                  f"{r['folds']} folds · remaining-days temperature = {label}.",
                  f"Cliff threshold: {r['threshold_rule']}. Skipped: {r['skipped'] or 'none'}. "
                  f"Seconds (fit+predict, all folds): {r['seconds']}.", "",
                  "### Overall", "",
                  "| model | MAPE | P10-P90 coverage (80% nominal) | Brier | precision | recall | base rate |",
                  "|---|---|---|---|---|---|---|"]
        for m, x in r["overall"].items():
            lines.append(f"| {m} | {_fmt(x['mape'])} | {_fmt(x['coverage_80'])} | {_fmt(x['brier'], False)} | "
                         f"{_fmt(x['precision'])} | {_fmt(x['recall'])} | {_fmt(x['base_rate'])} |")
        models = list(r["by_cut"])
        cuts = r["cuts"]
        lines += ["", "### MAPE of final units by cut day", "", "| model | " + " | ".join(f"day {c}" for c in cuts) + " |",
                  "|---|" + "---|" * len(cuts)]
        for m in models:
            lines.append(f"| {m} | " + " | ".join(_fmt(r["by_cut"][m][str(c)]["mape"]) for c in cuts) + " |")
        lines += ["", "### Brier score of the cliff call by cut day", "",
                  "| model | " + " | ".join(f"day {c}" for c in cuts) + " |", "|---|" + "---|" * len(cuts)]
        for m in models:
            lines.append(f"| {m} | " + " | ".join(_fmt(r["by_cut"][m][str(c)]["brier"], False) for c in cuts) + " |")
        if r.get("by_size"):
            lines += ["", "### MAPE by house size tercile (median cycle total)", "", "| model | small | mid | large |",
                      "|---|---|---|---|"]
            for m, x in r["by_size"].items():
                lines.append(f"| {m} | " + " | ".join(_fmt(x[t]["mape"]) for t in ("small", "mid", "large")) + " |")
        lines.append("")
    lines += ["## Caveats", "",
              "- PRECON homes (Lahore, 2018-19) are mostly large 3-phase houses; a household near 200 units is smaller. "
              "The target is the scale-free ratio final / (rate so far x 30), which is what transfers.",
              "- Windows overlap (30-day windows every 15 days), so rows are not independent within a house; "
              "folds are by house, so this does not leak across the train/test split.",
              "- naive and last_ratio are point forecasts, so their coverage and Brier are those of a 0/1 call.", ""]
    (ROOT / "docs" / "RESULTS.md").write_text("\n".join(lines))
