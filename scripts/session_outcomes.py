"""Household-level outcomes and case studies from results/session-aggregate.json (no new model runs).

  python scripts/session_outcomes.py   -> results/session-outcomes.json
"Arithmetic" = units so far / days elapsed x 30 > 200. "Alert" = verdict act or already_over (the only verdicts
that send a message). Case studies: at day 14, every cycle where exactly one of the two was on the right side.
"""
import json
from pathlib import Path

d = json.loads(Path("results/session-aggregate.json").read_text())
rows = d["rows"]
alert = lambda r: r["verdict"] in ("act", "already_over")  # noqa: E731
by_cut = {}
for cut in sorted({r["cut"] for r in rows}):
    g = [r for r in rows if r["cut"] == cut]
    crossed = [r for r in g if r["crossed"]]
    by_cut[cut] = {
        "cycles": len(g), "crossed": len(crossed),
        "alerts": sum(alert(r) for r in g), "alerts_real": sum(alert(r) and r["crossed"] for r in g),
        "arithmetic_over": sum(r["naive"] > 200 for r in g),
        "arithmetic_over_real": sum(r["naive"] > 200 and r["crossed"] for r in g),
        "model_only_right": sum(((r["p_cross"] >= 0.5) == r["crossed"]) and ((r["naive"] > 200) != r["crossed"])
                                for r in g),
        "arithmetic_only_right": sum(((r["p_cross"] >= 0.5) != r["crossed"]) and ((r["naive"] > 200) == r["crossed"])
                                     for r in g),
    }
first = {}
for r in sorted(rows, key=lambda r: r["cut"]):
    k = (r["house"], r["cycle_start"])
    if r["crossed"] and alert(r) and k not in first:
        first[k] = r["cut"]
crossed_cycles = {(r["house"], r["cycle_start"]) for r in rows if r["crossed"]}
warned = {"crossed_cycles": len(crossed_cycles),
          **{f"warned_by_day_{c}": sum(1 for k in crossed_cycles if first.get(k, 99) <= c) for c in (10, 14)},
          "never_warned": sum(1 for k in crossed_cycles if k not in first)}
cases = [r for r in rows if r["cut"] == 14 and (((r["p_cross"] >= 0.5) == r["crossed"]) != ((r["naive"] > 200) == r["crossed"]))]
out = {"source": "results/session-aggregate.json", "by_cut": by_cut, "warned": warned,
       "day14_disagreements": sorted(cases, key=lambda r: (r["house"], r["cycle_start"]))}
Path("results/session-outcomes.json").write_text(json.dumps(out, indent=1))
print(json.dumps({"day14": by_cut[14], "warned": warned}, indent=1))
for r in out["day14_disagreements"]:
    print(r["house"], r["cycle_start"], "final", r["final"], "arith", r["naive"], "p50", r["p50"],
          f"P {r['p_cross']:.0%}", r["verdict"])
