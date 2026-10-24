# memory.md: Slabwatch brain
> Read first, update last. Terse.

## What this is
Forecast a Pakistani household's end-of-cycle electricity units (P10/P50/P90) before the 200-unit protected cliff.
TabPFN quantiles of a scale-free ratio -> plain-code verdict + daily budget. Gemma reads meter photos/bills.
DEV Hacktoberfest Week 3. Deadline 2026-10-26 06:59 UTC. Spec: research repo
`outputs/hackathon-research/hacktoberfest-week3-2026-10/05-PIVOT-slabwatch.md`.

## Stack
Python 3.11 venv `.venv`. FastAPI on Render free (render.yaml). tabpfn-client (Render) / tabpfn 9.2 local [local].
sklearn GBM baseline. Open-Meteo. PRECON via CKAN (RAR; libarchive-c fallback). Temporal python SDK. Browserbase +
Playwright CDP. SerpApi. Tiger Cloud Postgres (timescaledb + pgvector, RRF). ntfy.sh.

## Status
- Scaffold done 2026-10-24. 38 tests pass (incl. Temporal time-skipping workflow test).
- PRECON houses 1-10 downloaded/extracted; features: 201 windows, 1407 rows. Backtest (naive/last_ratio/gbm) in docs/RESULTS.md.
- Not run yet (no keys): tabpfn_local, tabpfn_api, Gemma, Tiger, Browserbase, SerpApi, ntfy, Render deploy.
- No git yet (parent agent inits).

## Key decisions
- Target ratio = final / (rate_so_far x 30): PRECON homes 214-1271 units/cycle, users ~200.
- Days < 0.5 kWh are missing (logger dropouts in houses 2, 3, 10).
- GBM single-threaded (threadpoolctl): 150 s -> 12 s for the 5-fold backtest.
- P(cross): 11 quantiles -> piecewise-linear CDF.
- Alerts only on escalation to act/already_over.

## TO VERIFY
Gemma model id on AI Studio; PITC post-submit layout + captcha; embeddinggemma dim 768; Render 512 MB fit;
unar on House3/5 CRC; FCA query usefulness.

## File map
- `slabwatch/cli.py`: all commands · `config.py` env · `net.py` HTTP
- `data/precon.py` CKAN+extract+daily · `data/weather.py` Open-Meteo
- `features.py` rows + leakage-safe `cut_features` · `forecast.py` backends + p_cross · `decide.py` verdicts
- `evaluate.py` backtest -> docs/RESULTS.md · `service.py` glue · `web.py` + `static/index.html`
- `gemma.py` · `bill.py` · `tariff.py` · `store.py` + `sql/schema.sql` · `workflows.py` + `worker.py`
