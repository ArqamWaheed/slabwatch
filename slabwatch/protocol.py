"""Pre-registered dev/test evaluation (docs/PROTOCOL.md).

  python -m slabwatch protocol          # dev only: pick settings, fit calibration, write results/protocol-dev.json
  python -m slabwatch protocol --final  # also score the test homes ONCE -> results/protocol-test.json, docs/PROTOCOL-RESULTS.md

Dev = odd house numbers, test = even. All choices come from dev out-of-fold predictions.
"""
from __future__ import annotations

import datetime as dt
import json
import time

import numpy as np

from slabwatch.config import DATA, RESULTS, ROOT, settings
from slabwatch.features import feature_matrix
from slabwatch.forecast import GBM_PARAMS, QUANTILES, monotone, p_cross

LEVELS = np.array(QUANTILES)
FLOOR = 0.05   # ratio quantiles are clipped here: the cycle cannot end below 5% of the naive estimate
GBM_CANDIDATES = {
    "gbm_A": GBM_PARAMS,
    "gbm_B": {**GBM_PARAMS, "max_depth": 5, "min_samples_leaf": 20, "max_iter": 250},
    "gbm_C": {**GBM_PARAMS, "max_depth": 2, "min_samples_leaf": 80, "l2_regularization": 5.0},
}
TABPFN_CANDIDATES = {"tabpfn_ratio": False, "tabpfn_logratio": True}


# ------------------------------------------------------------------ models (ratio quantiles, shape (n, 11))
def fit_predict_gbm(params, Xtr, ytr, Xte):
    from sklearn.ensemble import HistGradientBoostingRegressor
    from threadpoolctl import threadpool_limits

    with threadpool_limits(1):
        cols = [HistGradientBoostingRegressor(**params, quantile=a, random_state=0).fit(Xtr, ytr).predict(Xte)
                for a in LEVELS]
    return monotone(np.column_stack(cols))


def fit_predict_tabpfn(log_target, Xtr, ytr, Xte, token):
    from tabpfn_client import TabPFNRegressor, set_access_token

    set_access_token(token)
    target = np.log(ytr) if log_target else ytr
    m = TabPFNRegressor(random_state=0).fit(Xtr, target)
    q = np.column_stack(m.predict(Xte, output_type="quantiles", quantiles=list(LEVELS)))
    return monotone(np.exp(q) if log_target else q)


def run_candidate(name, Xtr, ytr, Xte, token):
    if name in GBM_CANDIDATES:
        q = fit_predict_gbm(GBM_CANDIDATES[name], Xtr, ytr, Xte)
    else:
        q = fit_predict_tabpfn(TABPFN_CANDIDATES[name], Xtr, ytr, Xte, token)
    return np.maximum(q, FLOOR)  # raw quantiles can dip to <= 0, which breaks the log-space calibration


# ------------------------------------------------------------------ scoring
def pinball(y, q) -> float:
    """Mean pinball loss over all levels (ratio space)."""
    d = y[:, None] - q
    return float(np.mean(np.maximum(LEVELS * d, (LEVELS - 1) * d)))


def fit_calibration(y, q) -> np.ndarray:
    """Per-level shift in log space so that P(y <= shifted q_a) = a on these rows."""
    r = np.log(y)[:, None] - np.log(q)
    return np.array([np.quantile(r[:, i], a) for i, a in enumerate(LEVELS)])


def apply_calibration(q, shifts) -> np.ndarray:
    return monotone(q * np.exp(shifts)[None, :])


def score(df, q_ratio, T) -> dict:
    units = np.maximum(q_ratio * df["naive_units"].values[:, None], df["units_so_far"].values[:, None])
    final = df["final_units"].values
    i10, i50, i90 = (list(QUANTILES).index(a) for a in (0.1, 0.5, 0.9))
    pc = np.array([p_cross(T[i], QUANTILES, units[i]) for i in range(len(units))])
    over = final > T
    call = pc >= 0.5

    def block(idx):
        tp = int((call[idx] & over[idx]).sum())
        return {"n": int(idx.sum()),
                "pinball": pinball(df["ratio"].values[idx], q_ratio[idx]),
                "mape": float(np.mean(np.abs(units[idx, i50] - final[idx]) / final[idx])),
                "coverage_80": float(np.mean((final[idx] >= units[idx, i10]) & (final[idx] <= units[idx, i90]))),
                "brier": float(np.mean((pc[idx] - over[idx]) ** 2)),
                "precision": tp / call[idx].sum() if call[idx].sum() else None,
                "recall": tp / over[idx].sum() if over[idx].sum() else None}

    allidx = np.ones(len(df), bool)
    return {"overall": block(allidx),
            "by_cut": {int(c): block(df["cut"].values == c) for c in sorted(df["cut"].unique())}}


# ------------------------------------------------------------------ the protocol
def run(final: bool = False, weather: str = "clim") -> dict:
    import pandas as pd
    from sklearn.model_selection import GroupKFold

    s = settings()
    df = pd.read_parquet(DATA / "features.parquet").reset_index(drop=True)
    X = feature_matrix(df, weather).values
    y = df["ratio"].values
    houses = df["house"].values.astype(int)
    totals = df.drop_duplicates(["house", "cycle_start"]).groupby("house")["final_units"].median()
    T = df["house"].map(totals).values
    dev, test = houses % 2 == 1, houses % 2 == 0
    di = np.where(dev)[0]

    # 1) dev out-of-fold predictions for every candidate
    names = list(GBM_CANDIDATES) + (list(TABPFN_CANDIDATES) if s.tabpfn_token else [])
    oof, secs = {}, {}
    for n in names:
        t0, out = time.time(), np.zeros((len(di), len(LEVELS)))
        for tr, te in GroupKFold(n_splits=5).split(di, groups=houses[di]):
            out[te] = run_candidate(n, X[di[tr]], y[di[tr]], X[di[te]], s.tabpfn_token)
        oof[n], secs[n] = out, round(time.time() - t0, 1)
    dev_pinball = {n: pinball(y[di], q) for n, q in oof.items()}
    best_gbm = min(GBM_CANDIDATES, key=dev_pinball.get)
    chosen = {"gbm": best_gbm}
    if s.tabpfn_token:
        best_tab = min(TABPFN_CANDIDATES, key=dev_pinball.get)
        chosen["tabpfn"] = best_tab
        oof["blend"] = monotone((oof[best_gbm] + oof[best_tab]) / 2)
        dev_pinball["blend"] = pinball(y[di], oof["blend"])
        chosen["blend"] = "blend"
    calib = {k: fit_calibration(y[di], oof[v]) for k, v in chosen.items()}
    dev_scores = {k: {"raw": score(df.iloc[di], oof[v], T[di])["overall"],
                      "calibrated": score(df.iloc[di], apply_calibration(oof[v], calib[k]), T[di])["overall"]}
                  for k, v in chosen.items()}
    report = {"date_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "weather": weather,
              "dev_houses": sorted(set(houses[dev].tolist())), "test_houses": sorted(set(houses[test].tolist())),
              "dev_rows": int(dev.sum()), "test_rows": int(test.sum()), "dev_pinball": dev_pinball,
              "chosen": chosen, "calibration_shifts": {k: v.round(4).tolist() for k, v in calib.items()},
              "dev_scores": dev_scores, "dev_seconds": secs}
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "protocol-dev.json").write_text(json.dumps(report, indent=2, default=float))
    if not final:
        return report

    # 2) the one test run
    ti = np.where(test)[0]
    preds = {}
    for k, v in chosen.items():
        if k == "blend":
            continue
        preds[k] = run_candidate(v, X[di], y[di], X[ti], s.tabpfn_token)
    if "blend" in chosen:
        preds["blend"] = monotone((preds["gbm"] + preds["tabpfn"]) / 2)
    naive = np.ones((len(ti), len(LEVELS)))
    test_scores = {"naive": score(df.iloc[ti], naive, T[ti])}
    for k, q in preds.items():
        test_scores[k] = {"raw": score(df.iloc[ti], q, T[ti]),
                          "calibrated": score(df.iloc[ti], apply_calibration(q, calib[k]), T[ti])}
    report["test_scores"] = test_scores
    report["test_run_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    (RESULTS / "protocol-test.json").write_text(json.dumps(report, indent=2, default=float))
    write_md(report)
    return report


def _p(x, pct=True):
    return "-" if x is None else (f"{x * 100:.1f}%" if pct else f"{x:.4f}")


def write_md(r: dict) -> None:
    L = ["# Protocol results (dev/test, see PROTOCOL.md)", "",
         f"Test run {r['test_run_utc']} · weather `{r['weather']}` · dev homes {len(r['dev_houses'])} "
         f"({r['dev_rows']} rows) · test homes {len(r['test_houses'])} ({r['test_rows']} rows). Generated; do not edit.",
         "", "## Chosen on dev (mean pinball loss of the ratio, out-of-fold)", "",
         "| candidate | dev pinball |", "|---|---|"]
    L += [f"| {n} | {v:.5f} |" for n, v in sorted(r["dev_pinball"].items(), key=lambda kv: kv[1])]
    L += ["", f"Chosen: {r['chosen']}", "", "## Test homes, scored once", "",
          "| model | calibration | pinball | MAPE | P10-P90 coverage (80%) | Brier | precision | recall |",
          "|---|---|---|---|---|---|---|---|"]
    for k, v in r["test_scores"].items():
        for kind, sc in ([("-", v)] if k == "naive" else [("raw", v["raw"]), ("calibrated", v["calibrated"])]):
            o = sc["overall"]
            L.append(f"| {k} | {kind} | {_p(o['pinball'], False)} | {_p(o['mape'])} | {_p(o['coverage_80'])} | "
                     f"{_p(o['brier'], False)} | {_p(o['precision'])} | {_p(o['recall'])} |")
    cuts = sorted(int(c) for c in r["test_scores"]["naive"]["by_cut"])
    L += ["", "## Test MAPE by cut day (calibrated)", "", "| model | " + " | ".join(f"day {c}" for c in cuts) + " |",
          "|---|" + "---|" * len(cuts)]
    for k, v in r["test_scores"].items():
        bc = v["by_cut"] if k == "naive" else v["calibrated"]["by_cut"]
        L.append(f"| {k} | " + " | ".join(_p(bc[str(c)]["mape"] if str(c) in bc else bc[c]["mape"]) for c in cuts) + " |")
    (ROOT / "docs" / "PROTOCOL-RESULTS.md").write_text("\n".join(L) + "\n")
