# Evidence checklist (what proves each category)

Rule: a category is declared only if its artifact exists. Numbers only from files under `results/`.

| Category | Artifact that proves it | How to produce | Status |
|---|---|---|---|
| TabPFN | `docs/RESULTS.md` (all 41 homes incl. `tabpfn_api`); pre-registered test in `docs/PROTOCOL-RESULTS.md`, `results/protocol-test.json` | `backtest --models naive,last_ratio,gbm,tabpfn_api`; `protocol --final` | done |
| Session replay | `docs/SESSION.md`; `results/session-aggregate.json` (65 test-home cycles near 200, dev-only model); `results/session-api.json` (one cycle through `/api/forecast`) | `python scripts/replay_session.py aggregate` / `api URL` | done (replay of real PRECON homes, not a live family) |
| TabPFN (live) | `results/render-live-forecast.json` (backend blend) and `docs/images/app-live.png` | Render env `FORECAST_BACKEND=blend` | done |
| Render | https://slabwatch-ojcn.onrender.com; `render.yaml`; `/healthz` screenshot; `results/render-check-20261025.json`, `results/render-check-keys-20261025.json` | Blueprint deploy; keys as Render Secret Files | live: backend `blend`, Gemma photo reading on; forecast, meter photo, refusal and bill photo checked live 2026-10-25 |
| Gemma (meter) | `results/gemma/meter-eval.json` (+ `-v1`), one JSON per photo; truth in `eval/meter_truth.json` (17 CC photos) | `python scripts/eval_meters.py data/demo_meters` | done on demo photos; real household photos pending |
| Gemma (bill) | `results/bill-eval.json`; truth in `eval/bill_truth.json` (public sample bills); `results/session-bill-photo.json` (KE specimen through `/api/bill-photo`) | `python scripts/eval_bills.py data/sample_bills` | done on public samples |
| Temporal | logic: `tests/test_workflow.py` (time-skipping); dev-server smoke run (nudge -> signal -> forecast -> ntfy -> timer) noted in `memory.md` | `temporal server start-dev`, `worker`, `start-cycle` | smoke run done; UI screenshot + kill-and-resume log pending |
| PITC bill fetch | `results/bills/*.html` (form post reaches the portal; a dummy ref returns "invalid") | `python -m slabwatch fetch-bill --ref <14 digits>` | pending a real, consented reference number |
| Browserbase | `results/tariff/browserbase-*.json` (search + page read, Gemma quote check) | `python -m slabwatch tariff-watch` | done |
| Tiger Data | `db-init` (timescaledb + vector); `tariff-watch --search "FCA October"` with `mode: hybrid_rrf` | `db-init`, `tariff-watch --search ...` | done (terminal output; no saved file yet) |
