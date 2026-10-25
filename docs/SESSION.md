# Demo session: public meter photos, a sample bill, replayed households

Run 2026-10-25. Every number below is copied from a file under `results/`; the script that wrote it is named.
None of this is a live family. It uses public, consented or specimen inputs, because a household's own photos
and bill reference were not available before the deadline.

## 1. Meter photos (Gemma)

`scripts/eval_meters.py` -> `results/gemma/meter-eval.json` (one JSON per photo next to it). Model `gemma-4-26b-a4b-it`.

The inputs are 17 Creative Commons photos of electricity meters found through Openverse (Flickr and Wikimedia
Commons; creator, licence and link for each are in `eval/meter_truth.json`). The images are not in the repo. I
labelled each one by eye from the full-resolution file before running the model:

- **read** (4): a single kWh register is clearly visible. It is correct only if the reading matches.
- **refuse** (10): too far, steep angle, nameplate only, several meters, or a non-kWh screen. It is correct only if
  the model returns no reading.
- **ambiguous** (3): a number is visible, but I could not tell whether it is the full kWh total. These are
  reported but not scored.

| run | prompt | read: correct / wrong / refused | refuse: refused / guessed | ambiguous (not scored) |
|---|---|---|---|---|
| v1 (`meter-eval-v1.json`) | as shipped on 2026-10-24 | 4 / 0 / 0 | 9 / 1 | 25391.3 · refused · 1 |
| v2 (`meter-eval.json`) | + "more than one meter in the photo -> refuse" | 3 / 1 / 0 | 10 / 0 | 25391.3 · refused · 1 |

- The v1 guess was the bank of 15 meters (m09): it read 5895 off one of them. The added rule is a tightening, and
  in v2 all three multi-meter photos were refused with that reason.
- The v2 miss: on the Actaris drum (m04, 01967 plus a red tenths drum showing 6) it returned **19676** with
  confidence 1.0, so the tenths digit was read as a whole digit. v1 read 1967.6 from the same image, so the
  output is not stable at temperature 0. In the app a 10x jump would fail `check_against_previous`, which asks the
  family to confirm, but a first reading has nothing to compare against. This is a known failure mode, not fixed.
  I did not tune the prompt again on these photos.
- Ambiguous: m07 came back as 25391.3 (I had seen 5391.3 with a possible hidden leading digit). The Pakistani
  FESCO/PEL meter (m16) was refused because its screen 016 is not the total kWh register. The cut-off Elster LCD
  (m17) came back as 1.
- Each photo call took 7.2-79.1 s across both runs (AI Studio free tier, with retries on 429/503).

## 2. A bill (KE specimen through the web API)

`POST /api/bill-photo` with K-Electric's own specimen bill (dummy customer, July 2025 layout) ->
`results/session-bill-photo.json`.

- Current units: read 179, printed 179.
- 13-month history: 7 of 13 months exact. The last three months came back shifted one month early, and July 2025
  is missing. This matches the earlier bill eval of the same image (`results/bill-eval.json`).

The PITC portal fetch still needs a real, consented 14-digit reference number. The publicly posted sample bills
that show one are of real consumers, so I did not use them.

## 3. Replayed households (forecast + verdict)

PRECON households agreed to have their consumption published (LUMS, CC0). The model is fitted on the **dev** homes
only (odd house numbers, [PROTOCOL.md](PROTOCOL.md)). Every replayed cycle comes from a **test** home. These rules
were fixed in `scripts/replay_session.py` before it ran:

- cycles that end within 200 ± 40 units;
- the real 200-unit rule;
- climatology for the remaining-days weather (aggregate run).

### All 65 such cycles (13 test homes), `results/session-aggregate.json`

41.5% of these cycles ended at or under 200 units, and 58.5% went over. "Side right" means the model's
P(over 200) ≥ 0.5 matched what happened. Naive multiplies the current rate out to 30 days. Brier is the error of
P(over 200); the base rate always predicts 58.5%.

| cut day | Brier (model) | Brier (base rate) | side right (model) | side right (naive) | P10-P90 cover | crossed but told "safe" |
|---|---|---|---|---|---|---|
| 5 | 0.2097 | 0.2428 | 69.2% | 66.2% | 87.7% | 1 |
| 7 | 0.1808 | 0.2428 | 75.4% | 72.3% | 83.1% | 0 |
| 10 | 0.1468 | 0.2428 | 78.5% | 73.8% | 81.5% | 1 |
| 14 | 0.1102 | 0.2428 | 84.6% | 75.4% | 86.2% | 2 |
| 18 | 0.1045 | 0.2428 | 87.7% | 81.5% | 84.6% | 1 |
| 21 | 0.0791 | 0.2428 | 87.7% | 86.2% | 83.1% | 1 |
| 25 | 0.0363 | 0.2428 | 93.8% | 93.8% | 89.2% | 0 |

Read it as: by mid-cycle the model calls the side of 200 correctly more often than multiplying out. The edge over
naive is largest around days 10-18 and gone by day 25. These are 65 cycles from 13 homes, overlapping 15-day
windows of the same homes, so the cycles are not independent.

### One cycle through the running app, `results/session-api.json`

The app (`uvicorn slabwatch.web:app`, calibrated blend, trained on the dev homes only) was sent readings on
days 3, 7, 10, 14, 18, 21 and 25 of house 36's cycle from 2019-01-12. By the rule above this is the band's cycle
that ended closest to 200, so it is the hardest call in the set. It ended at **200.5** units, and the previous
30 days were 198.6. For this past cycle the app looked up archive temperatures, so its "forecast" weather was the
real weather.

| day | used | P10 | P50 | P90 | P(over 200) | verdict |
|---|---|---|---|---|---|---|
| 3 | 21.3 | 183.5 | 209.3 | 273.8 | 64% | act |
| 7 | 50.3 | 191.4 | 210.7 | 256.0 | 74% | act |
| 10 | 73.3 | 199.7 | 216.9 | 251.6 | 89% | act |
| 14 | 99.7 | 198.5 | 210.8 | 230.8 | 85% | act |
| 18 | 125.6 | 196.1 | 205.4 | 220.5 | 76% | act |
| 21 | 143.0 | 193.4 | 199.7 | 208.9 | 48% | watch |
| 25 | 168.7 | 195.3 | 199.2 | 204.6 | 44% | watch |

The day-25 message: "Probably fine, but close: 168.7 units in 25 days. Staying under 200 means about 6.3
units/day for the last 5 days (you're at 6.7)." The house finished 0.5 units over. The P10-P90 band contained the
outcome every day, but after day 18 the verdict leaned the wrong way on a coin-flip finish.

The first forecast after the server started took 41.2 s. That server trained on a dev-only feature file that has
no saved GBM, so it fitted from scratch; later forecasts took 1.6-7.4 s. The shipped GBM
(`slabwatch export-gbm`) covers the rows Render uses.
