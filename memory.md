# memory.md: Slabwatch brain
> Read first, update last. Terse.

## What this is
Forecast a Pakistani household's end-of-cycle electricity units (P10/P50/P90) before the 200-unit protected cliff.
Calibrated GBM+TabPFN blend on a scale-free ratio -> plain-code verdict + daily budget. Gemma reads meter photos/bills.
DEV Hacktoberfest Week 3. Deadline 2026-10-26 06:59 UTC. Spec: research repo
`outputs/hackathon-research/hacktoberfest-week3-2026-10/05-PIVOT-slabwatch.md`.

## Stack
Python 3.11 venv `.venv`. FastAPI on Render free (render.yaml). tabpfn-client (Render) / tabpfn local [local].
sklearn GBM. Open-Meteo. PRECON via CKAN. Temporal python SDK. Browserbase (tariff news only). Tiger Cloud Postgres
(timescaledb + pgvector, RRF). ntfy.sh. SerpApi removed (user: doesn't work).

## Key decisions
- Target ratio = final / (rate_so_far x 30). Days < 0.5 kWh = missing.
- Default FORECAST_BACKEND=blend (assets/calibration.json); TabPFN alone lost the pre-registered test.
- GBM fit cached by fingerprint (`Forecaster(cache=True)`, only service.model): shipped `assets/gbm-*.pkl.gz` for
  the train asset rows (`slabwatch export-gbm`; rerun after train_rows or GBM_PARAMS_B change), else data/cache.
  Blend fits GBM + TabPFN in parallel. Render-path blend cold start ~10 s locally (was ~30 s).
- Render live: https://slabwatch-ojcn.onrender.com (user deployed 998d2be, backend gbm, no secrets). Open-Meteo 429s from
  Render IPs -> temps_for falls back to shipped climatology asset and the message says so. Ships 2 GBMs (blend B + plain gbm).
- PITC fetch = local form post (Browserbase IPs time out). Alerts only on escalation.
- 41 PRECON homes: 65 test-home cycles end within 200 +/- 40 (memory's old "214-1271" was houses 1-10 only).

## Evidence (docs/EVIDENCE.md is the table; docs/SESSION.md the demo write-up)
- Protocol test, backtest, Browserbase tariff watch, Tiger hybrid search, Temporal smoke: done.
- 2026-10-25: Gemma on 17 CC meter photos (eval/meter_truth.json, images in data/demo_meters, git-ignored);
  v1: 4/4 read, 9/10 refused (guessed on multi-meter). Added "several meters -> refuse"; v2: 3/4 (m04 read 19676 for 1967.6, conf 1.0: red tenths drum), 10/10 refused. Do not retune on these photos.
- Session replay (scripts/replay_session.py): dev-only model; aggregate + one cycle via /api/forecast.
- KE specimen via /api/bill-photo: 7/13 months (last months shifted).

## Still open
- Render secrets: user must paste TABPFN_TOKEN, GOOGLE_API_KEY (+DATABASE_URL, NTFY_TOPIC) in Render Environment, then
  FORECAST_BACKEND=blend (I may not type secrets into forms). Live forecast verified 200 on gbm after the fallback.
- DEV post: draft saved on dev.to (unpublished, 2026-10-25); source `../articlewriting/hacktoberfest-week3-slabwatch.md`.
  Images in docs/images (scripts/post_images.py from results/ + 2 Google Flow illustrations). Update the Demo paragraph
  once keys are on Render.
- `gemma.check_against_previous()` is not called anywhere (post says so; wire into /api/reading after deadline).
- Real consented bill ref, real household photos / live family, Temporal UI screenshot + kill/resume log.
TO VERIFY: embeddinggemma dim 768; Render 512 MB fit with blend; PITC post-submit layout + captcha; unar on House3/5 CRC.

## File map
- `slabwatch/cli.py`: all commands · `config.py` env · `net.py` HTTP
- `data/precon.py` CKAN+extract+daily · `data/weather.py` Open-Meteo
- `features.py` rows + leakage-safe `cut_features` · `forecast.py` backends + p_cross + GBM cache · `decide.py`
- `evaluate.py` backtest · `protocol.py` dev/test · `service.py` glue · `web.py` + `static/index.html`
- `gemma.py` · `bill.py` · `bill_estimate.py` · `tariff.py` · `store.py` + `sql/schema.sql` · `workflows.py` + `worker.py`
- `scripts/`: backtest, eval_bills, eval_meters, replay_session
