# Evidence checklist (what proves each category)

Rule: a category is declared only if its artifact exists. Numbers only from files under `results/`.

| Category | Artifact that proves it | How to produce | Status |
|---|---|---|---|
| TabPFN | `docs/RESULTS.md` rows for `tabpfn_local` / `tabpfn_api` next to naive / last_ratio / gbm; `results/backtest-*-latest.json` | `python -m slabwatch backtest --models naive,last_ratio,gbm,tabpfn_local --sample 3000` | naive/last_ratio/gbm done (houses 1-10); TabPFN pending (token) |
| TabPFN (live) | Screenshot of the page with backend `tabpfn_api` and the P10-P90 band | Render env `FORECAST_BACKEND=tabpfn_api` | pending |
| Render | Live onrender.com URL; `render.yaml`; screenshot of `/healthz`; cold-start timing (page's "Server awake (N s)") | Blueprint deploy | pending |
| Gemma | Table: N real meter photos -> read / refused / correct; JSON per photo under `results/gemma/` | `python -m slabwatch add-reading --photo ...` per photo | pending |
| Temporal | Temporal UI screenshot of `slabwatch-cycle-<id>` with a timer; log of kill-worker-and-resume | `temporal server start-dev`, `worker`, `start-cycle`; kill and restart worker | logic tested on time-skipping server (tests/test_workflow.py) |
| Browserbase | Session replay link/screenshot of a real PITC fetch; `results/bills/*.png` | `python -m slabwatch fetch-bill --ref <14 digits>` | pending (selectors TO VERIFY; captcha placeholder seen) |
| SerpApi | `results/tariff/serpapi-*.json` query log; one doc cited in a rupee estimate | `python -m slabwatch tariff-watch` | pending |
| Tiger Data | `db-init` output showing timescaledb + vector; one `tariff-watch --search` result with `mode: hybrid_rrf` | `db-init`, `tariff-watch`, `tariff-watch --search "FCA October"` | pending |
