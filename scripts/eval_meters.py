"""Score Gemma's meter reading on demo CC photos against hand labels (eval/meter_truth.json).

  python scripts/eval_meters.py data/demo_meters
Prints and saves results/gemma/meter-eval.json (one JSON per photo next to it).
read: correct if reading_kwh is in `accept`; refuse: correct if the model (or validation) refused.
"""
import json
import sys
import time
from pathlib import Path

from slabwatch.gemma import Refused, read_meter

root = Path(sys.argv[1] if len(sys.argv) > 1 else "data/demo_meters")
truth = json.loads(Path("eval/meter_truth.json").read_text())
outdir = Path("results/gemma")
outdir.mkdir(parents=True, exist_ok=True)
rows, tally = {}, {"read_correct": 0, "read_wrong": 0, "read_refused": 0, "refuse_ok": 0, "refuse_guessed": 0}
for name, t in truth.items():
    if name.startswith("_") or not (root / name).exists():
        continue
    t0 = time.time()
    try:
        got = read_meter(root / name)
    except Refused as e:
        got = {"reading_kwh": None, "unreadable_reason": f"validation: {e}"}
    except Exception as e:  # noqa: BLE001
        got = {"reading_kwh": None, "error": str(e)[:200]}
    r = got.get("reading_kwh")
    if t["expect"] == "read":
        lo, hi = t["accept"]
        outcome = "refused" if r is None else ("correct" if lo <= r <= hi else "wrong")
        tally[f"read_{outcome}"] += 1
    elif t["expect"] == "refuse":
        outcome = "refused_ok" if r is None else "guessed"
        tally["refuse_ok" if r is None else "refuse_guessed"] += 1
    else:
        outcome = "refused" if r is None else f"read {r:g}"
    rows[name] = {"expect": t["expect"], "truth_kwh": t.get("kwh"), "outcome": outcome, "model": got,
                  "seconds": round(time.time() - t0, 1)}
    (outdir / f"{Path(name).stem}.json").write_text(json.dumps(rows[name], indent=1))
    print(f"{name[:40]:40} {t['expect']:9} -> {outcome:12} {got.get('display_label')!s:8} "
          f"conf {got.get('confidence')} | {got.get('unreadable_reason') or ''}"[:200])
summary = {**tally, "model": None, "per_photo": rows}
try:
    from slabwatch.config import settings
    summary["model"] = settings().gemma_model
except Exception:  # noqa: BLE001
    pass
(outdir / "meter-eval.json").write_text(json.dumps(summary, indent=1))
print("TOTAL", json.dumps(tally))
