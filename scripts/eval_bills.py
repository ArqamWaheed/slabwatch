"""Score Gemma's bill reading against hand-transcribed units (eval/bill_truth.json).

  python scripts/eval_bills.py data/sample_bills
Prints and saves results/bill-eval.json. Only months and units are compared or saved.
"""
import json
import sys
import time
from pathlib import Path

from slabwatch.gemma import read_bill_image

root = Path(sys.argv[1] if len(sys.argv) > 1 else "data/sample_bills")
truth = json.loads(Path("eval/bill_truth.json").read_text())
out, tot_ok, tot_n, tot_extra = {}, 0, 0, 0
for name, t in truth.items():
    if name.startswith("_") or not (root / name).exists():
        continue
    t0 = time.time()
    try:
        got = read_bill_image(root / name)
    except Exception as e:  # noqa: BLE001
        got = {"history": [], "error": str(e)[:200]}
    read = {h["month"]: h["units"] for h in got.get("history", [])}
    ok = sum(1 for m, u in t["history"].items() if read.get(m) == u)
    extra = sum(1 for m in read if m not in t["history"])
    wrong = {m: [u, read.get(m)] for m, u in t["history"].items() if read.get(m) != u}
    out[name] = {"months": len(t["history"]), "exact": ok, "invented_months": extra, "wrong_or_missing": wrong,
                 "current_units": [t["current_units"], got.get("current_units")], "seconds": round(time.time() - t0, 1),
                 "error": got.get("error")}
    tot_ok, tot_n, tot_extra = tot_ok + ok, tot_n + len(t["history"]), tot_extra + extra
    print(name, f"{ok}/{len(t['history'])} exact, {extra} invented, current {out[name]['current_units']}", wrong or "")
summary = {"exact": tot_ok, "months": tot_n, "invented_months": tot_extra, "per_bill": out}
Path("results").mkdir(exist_ok=True)
Path("results/bill-eval.json").write_text(json.dumps(summary, indent=1))
print(f"TOTAL {tot_ok}/{tot_n} months exact, {tot_extra} invented")
