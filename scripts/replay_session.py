"""Replay real PRECON households as if a family typed in their meter readings, with no leakage.

PRECON households agreed to have their consumption published (Open Data Pakistan, CC0). The model is fitted on the
dev homes only (odd house numbers, docs/PROTOCOL.md); every replayed cycle comes from a test home (even number).

  python scripts/replay_session.py aggregate      # every test-home cycle ending 160-240 units, cuts 5..25
  python scripts/replay_session.py api URL        # one cycle through a running web app's /api/forecast
                                                   # (start it with SLABWATCH_DATA=<dir with dev-only features>)
Rules fixed before running: the cycle band is 200 +/- 40 units; the API cycle is the band's cycle whose final total is
closest to 200 (the hardest call); readings arrive on days 3, 7, 10, 14, 18, 21, 25.
Writes results/session-aggregate.json or results/session-api.json.
"""
import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

THRESHOLD, BAND, READ_DAYS = 200.0, 40.0, (3, 7, 10, 14, 18, 21, 25)
OUT = Path("results")


def band_cycles(df):
    w = df.groupby(["house", "cycle_start"])["final_units"].first().reset_index()
    return w[(w.house % 2 == 0) & ((w.final_units - THRESHOLD).abs() <= BAND)]


def aggregate():
    from slabwatch.config import settings
    from slabwatch.decide import decide
    from slabwatch.features import feature_matrix
    from slabwatch.forecast import QUANTILES, Forecaster, p_cross

    df = pd.read_parquet("data/features.parquet")
    dev = df[df.house % 2 == 1]
    dev = dev.sample(min(3000, len(dev)), random_state=0)  # same TabPFN context cap as the app
    cyc = band_cycles(df)
    test = df.merge(cyc[["house", "cycle_start"]], on=["house", "cycle_start"])
    t0 = time.time()
    f = Forecaster("blend", token=settings().tabpfn_token).fit(feature_matrix(dev, "clim").values, dev["ratio"].values)
    rq = f.predict_ratio_quantiles(feature_matrix(test, "clim").values)
    units = np.maximum(rq * test["naive_units"].values[:, None], test["units_so_far"].values[:, None])
    rows = []
    for i, r in enumerate(test.itertuples()):
        q = units[i]
        pc = p_cross(THRESHOLD, QUANTILES, q)
        p10, p50, p90 = (float(np.interp(a, QUANTILES, q)) for a in (0.1, 0.5, 0.9))
        d = decide(p10, p50, p90, pc, r.units_so_far, int(r.cut), 30, THRESHOLD, 6, backend="blend")
        rows.append({"house": int(r.house), "cycle_start": str(r.cycle_start)[:10], "cut": int(r.cut),
                     "final": round(r.final_units, 1), "crossed": bool(r.final_units > THRESHOLD),
                     "naive": round(r.naive_units, 1), "p50": round(p50, 1), "p10": round(p10, 1),
                     "p90": round(p90, 1), "p_cross": round(pc, 3), "verdict": d.verdict})
    res = pd.DataFrame(rows)
    by_cut = {}
    for cut, g in res.groupby("cut"):
        y = g.crossed.astype(float)
        by_cut[int(cut)] = {
            "n": len(g),
            "brier_model": round(float(((g.p_cross - y) ** 2).mean()), 4),
            "brier_base_rate": round(float(((y.mean() - y) ** 2).mean()), 4),
            "side_right_model": round(float(((g.p_cross >= 0.5) == g.crossed).mean()), 3),
            "side_right_naive": round(float(((g.naive > THRESHOLD) == g.crossed).mean()), 3),
            "cover_p10_p90": round(float(((g.final >= g.p10) & (g.final <= g.p90)).mean()), 3),
            "verdicts": g.verdict.value_counts().to_dict(),
            "act_or_over_when_crossed": int(((g.verdict.isin(["act", "already_over"])) & g.crossed).sum()),
            "safe_when_crossed": int(((g.verdict == "safe") & g.crossed).sum()),
        }
    out = {"what": "test-home cycles ending 200 +/- 40 units, model fitted on dev homes, climatology weather",
           "cycles": int(len(cyc)), "houses": sorted(int(h) for h in cyc.house.unique()),
           "crossed_share": round(float(cyc.final_units.gt(THRESHOLD).mean()), 3),
           "seconds": round(time.time() - t0, 1), "by_cut": by_cut, "rows": rows}
    OUT.mkdir(exist_ok=True)
    (OUT / "session-aggregate.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))


def api(url: str):
    from slabwatch.net import post_json

    df = pd.read_parquet("data/features.parquet")
    cyc = band_cycles(df)
    pick = cyc.iloc[(cyc.final_units - THRESHOLD).abs().argsort().iloc[0]]
    house, start = int(pick.house), pd.Timestamp(pick.cycle_start).date()
    daily = pd.read_parquet("data/precon/daily.parquet").query("house == @house").set_index("date")["kwh"]
    daily.index = pd.to_datetime(daily.index).date
    meta_row = pd.read_parquet("data/precon/metadata.parquet").query("house == @house").iloc[0]
    meta = {k: float(meta_row[k]) for k in ("n_acs", "area_sqft", "people")}
    prev = float(sum(daily.get(start - dt.timedelta(days=i), 0.0) for i in range(1, 31)))

    def used(k):  # units on the meter at the reading taken on cycle_start + k (covers days 0..k-1)
        return float(sum(daily.get(start + dt.timedelta(days=i), 0.0) for i in range(k)))

    start_reading = 10000.0  # PRECON has no register values; any start works because only differences matter
    steps, readings = [], []
    for k in READ_DAYS:
        readings.append({"date": str(start + dt.timedelta(days=k)), "reading_kwh": round(start_reading + used(k), 1)})
        body = {"cycle_start": str(start), "start_reading": start_reading, "readings": readings,
                "prev_cycle_units": round(prev, 1), "meta": meta, "threshold": THRESHOLD}
        t0 = time.time()
        r = post_json(f"{url}/api/forecast", body, timeout=300)
        f, d = r["forecast"], r["decision"]
        steps.append({"day": k, "reading": readings[-1]["reading_kwh"], "used_so_far": round(used(k), 1),
                      "p10": round(f["p10"], 1), "p50": round(f["p50"], 1), "p90": round(f["p90"], 1),
                      "p_cross": round(f["p_cross"], 3), "naive": round(f["naive_units"], 1),
                      "verdict": d["verdict"], "message": d["message"], "backend": f["backend"],
                      "seconds": round(time.time() - t0, 1)})
        print(f"day {k:2} used {used(k):6.1f}  P10 {f['p10']:6.1f} P50 {f['p50']:6.1f} P90 {f['p90']:6.1f}  "
              f"P(>200) {f['p_cross']:.0%}  [{d['verdict']}]  {steps[-1]['seconds']} s")
    out = {"what": "one test-home cycle replayed through /api/forecast; the app looks up Open-Meteo archive temps for this past cycle, so its remaining-days weather is the actual weather (a perfect forecast)", "url": url, "house": house,
           "cycle_start": str(start), "final_units": round(used(30), 1), "prev_cycle_units": round(prev, 1),
           "meta": meta, "steps": steps}
    OUT.mkdir(exist_ok=True)
    (OUT / "session-api.json").write_text(json.dumps(out, indent=1))
    print(f"actual final: {used(30):.1f} units")


if __name__ == "__main__":
    {"aggregate": lambda: aggregate(), "api": lambda: api(sys.argv[2].rstrip("/"))}[sys.argv[1]]()
