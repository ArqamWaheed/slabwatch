# Architecture

```
                         once: 14-digit reference no.
  household ──────────────────────────────────────────────┐
     │  meter photo / typed reading (days 5,10,15,20,25)  │
     ▼                                                    ▼
 ┌──────────────────────── Render (free web) ──────────────────────┐     ┌──── laptop / worker ────┐
 │ FastAPI  slabwatch/web.py                                       │     │ Temporal worker          │
 │  /            static/index.html (band, P(cross), budget)        │     │  CycleWorkflow per home  │
 │  /api/photo   ─► gemma.read_meter ─► Gemma (AI Studio | Ollama) │     │  sleep ► nudge (ntfy)    │
 │  /api/forecast─► service.forecast_cycle                         │     │  wait signal ► forecast  │
 │                   features.cut_features  (readings ► features)  │     │  alert once/escalation   │
 │                   data/weather  (Open-Meteo past 14 + next 16 d)│     │  end+3d ► bill + score   │
 │                   forecast.Forecaster    (TabPFN API | GBM)     │     │  continue_as_new         │
 │                   decide.decide          (plain code verdict)   │     └──────────┬───────────────┘
 │  /api/reading ─► store.add_reading ─► signal CycleWorkflow ─────┼────────────────┘
 │  /healthz     (no external calls)                               │
 └──────────────┬──────────────────────────────────────────────────┘
                │ psycopg
                ▼
 ┌──── Tiger Cloud Postgres ────────────────────────────────────────┐
 │ households · readings (hypertable) · cycles · forecasts (hyper)  │
 │ tariff_docs: tsvector GIN + pgvector HNSW ─► RRF hybrid search   │
 └──────────────▲───────────────────────────────▲───────────────────┘
                │ bill history                  │ FCA / tariff news
        bill.fetch_bill (Browserbase +          tariff.watch (SerpApi google + google_news)
        Playwright CDP ► bill.pitc.com.pk)

 Offline (laptop): data/precon.py ► daily.parquet ► features.build_rows ► evaluate.run_backtest
                   ► docs/RESULTS.md, results/*.json ; export ► slabwatch/assets/train_rows.parquet
```

## Who does what
| Piece | Job | Never does |
|---|---|---|
| TabPFN (or GBM) | Quantiles (5%..95%) of `ratio = final / (rate so far x cycle days)` | Decide what to tell the user |
| `decide.py` | Verdict, daily budget, message, assumptions | Call a model |
| Gemma | Read meter digits / bill text into strict JSON, or refuse | Produce numbers that skip validation |
| Temporal | When to ask, when to re-forecast, when to fetch the bill | I/O inside workflow code |

## Why the ratio target
PRECON homes use 214-1271 units in a median 30-day window (houses 1-10). A household near 200 is smaller.
The ratio to the multiply-it-out estimate is scale-free (tests/test_features.py) so big homes teach the shape
of a cycle (heat, weekends, recent trend) without teaching their size.

## P(cross)
11 predicted quantiles -> piecewise-linear CDF, tails extended with the outer slope and clipped (forecast.py).
