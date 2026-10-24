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

## Build log 2026-10-24 (to ~13:00 UTC)
- Data: 41/42 PRECON houses (one archive member missing), 884 windows, 6188 rows.
- Backtest (clim weather, GroupKFold by house): naive 11.5% MAPE; gbm 8.2% (P10-P90 cover 77%); tabpfn_api 8.6% (cover 87%, too wide). Honest: TabPFN ~= GBM; GBM params were picked on houses 1-10 (bias toward GBM).
- TabPFN local 3.5 on CPU too slow (fit 1000 rows 123 s); use tabpfn_api (fit 4000 + predict 1000 in 15 s). Thinking Mode: regression supports output_type=mean only -> not usable for quantiles.
- Gemma: AI Studio key lists gemma-4-26b-a4b-it / gemma-4-31b-it. Thought parts are skipped; responseMimeType JSON works; retry on 429/503. Synthetic LCD read 4527.3 correctly (19 s).
- Browserbase: PITC / lesco.gov.pk time out and nepra.org.pk gives a Cloudflare 403 from its IPs. New job: tariff watcher (Browserbase search + session reads news -> Gemma extracts FCA -> code checks the quote is on the page). Found Rs1.11 (Aug 2026 FCA, Oct bills) from Tribune; refused Dawn's Rs1.1086 because Gemma rounded it.
- SerpApi dropped (user: doesn't work).
- PITC bill: local form post (works; dummy ref -> "Given Ref/App No is invalid"). Needs the real 14-digit ref.
- Tiger Cloud: free shared service "slabwatch" (us-east-1), timescaledb 2.31 + pgvector; hypertables readings/forecasts; hybrid RRF search over tariff_docs works (bge-base-en-v1.5 local embeddings).
- Temporal: CLI 1.9.1 dev server (data/temporal/dev.db, UI :8233) + worker; smoke test nudge->signal->forecast->ntfy alert->timer passed, then cleaned up.
- Web: /api/forecast with tabpfn_api ~11 s cold.
- BLOCKED: Render deploy (Chrome extension denied on dashboard.render.com).
- NEED FROM USER: allow Render in the extension (or a Render API key), 14-digit bill ref + DISCO, meter photos, the family session.
