"""Command line. Heavy imports live inside each command so `--help` works with no dependencies."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=str, ensure_ascii=False))


def cmd_doctor(a: argparse.Namespace) -> int:
    from slabwatch.config import DATA, settings

    s = settings()
    print(f"forecast backend: {s.forecast_backend} | gemma: {s.gemma_provider}/{s.gemma_model} | "
          f"threshold {s.slab_threshold:g} units, penalty {s.penalty_months} months, cycle {s.cycle_days} d, "
          f"lat/lon {s.lat},{s.lon}")
    keys = {
        "TABPFN_TOKEN (tabpfn_api; also accepts local 3.5 licence)": s.tabpfn_token,
        "GOOGLE_API_KEY (Gemma via AI Studio)": s.google_api_key if s.gemma_provider == "google" else "n/a",
        "DATABASE_URL (Tiger Cloud Postgres)": s.database_url,
        "BROWSERBASE_API_KEY": s.browserbase_api_key,
        "NTFY_TOPIC": s.ntfy_topic,
    }
    for k, v in keys.items():
        print(f"[{'ok' if v else '--'}] {k}" + ("  (provider is ollama)" if v == "n/a" else ""))
    print(f"[ok] TEMPORAL_ADDRESS={s.temporal_address}")
    for mod, why in (("numpy", "core"), ("pandas", "core"), ("sklearn", "gbm backend"), ("pyarrow", "parquet"),
                     ("fastapi", "web"), ("tabpfn_client", "tabpfn_api"), ("tabpfn", "tabpfn_local [local]"),
                     ("psycopg", "store"), ("temporalio", "workflows"), ("browserbase", "bill fetch"),
                     ("playwright", "bill fetch"), ("libarchive", "RAR fallback extractor")):
        try:
            __import__(mod)
            print(f"[ok] import {mod:<14} ({why})")
        except (ImportError, OSError):
            print(f"[--] import {mod:<14} ({why})")
    from slabwatch.data.precon import DAILY, EXTRACTED, _cli_extractor

    print(f"[{'ok' if _cli_extractor() else '--'}] RAR CLI extractor (unar/unrar/7z)")
    n = len(list(EXTRACTED.glob('House*.csv'))) if EXTRACTED.exists() else 0
    print(f"[{'ok' if n else '--'}] PRECON extracted houses: {n}  ({EXTRACTED})")
    print(f"[{'ok' if DAILY.exists() else '--'}] daily.parquet   [{'ok' if (DATA / 'features.parquet').exists() else '--'}]"
          f" features.parquet")
    if a.ping:
        return _ping(a.ping, s)
    return 0


def _ping(what: str, s) -> int:
    try:
        if what == "weather":
            from slabwatch.data.weather import forecast
            f = forecast(s.lat, s.lon)
            print(f"open-meteo: {len(f)} days, first {min(f)}")
        elif what == "tiger":
            from slabwatch import store
            with store.connect() as c:
                print(c.execute("SELECT extname, extversion FROM pg_extension ORDER BY 1").fetchall())
        elif what == "gemma":
            from slabwatch.gemma import _ask
            print(_ask('Return {"ok": true} as JSON.', None, "text/plain", {"type": "object"}, s))
        elif what == "ntfy":
            from slabwatch.service import notify
            print("ntfy status", notify("Slabwatch doctor test"))
        elif what == "browserbase":
            from slabwatch.tariff import search
            print(len(search("NEPRA fuel charges adjustment", s=s)), "Browserbase search results")
        elif what == "tabpfn":
            import numpy as np

            from slabwatch.forecast import Forecaster
            X = np.random.default_rng(0).normal(size=(60, 3))
            f = Forecaster("tabpfn_api", token=s.tabpfn_token).fit(X, X[:, 0])
            print("tabpfn_api quantiles:", f.predict_ratio_quantiles(X[:2]).round(3).tolist())
        elif what == "temporal":
            from slabwatch.workflows import client
            asyncio.run(client())
            print("temporal: connected")
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] {what}: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_fetch_data(a: argparse.Namespace) -> int:
    from slabwatch.data.precon import fetch_and_build

    _print(fetch_and_build(a.houses))
    return 0


def cmd_build_features(a: argparse.Namespace) -> int:
    import pandas as pd

    from slabwatch.config import DATA, settings
    from slabwatch.data import precon, weather
    from slabwatch.features import build_rows
    from slabwatch.service import export_train_asset

    s = settings()
    daily = pd.read_parquet(precon.DAILY)
    meta = pd.read_parquet(precon.META)
    start, end = daily["date"].min().date(), daily["date"].max().date()
    temps = {k: v["tmean"] for k, v in weather.archive(start, end, s.lat, s.lon).items()}
    clim = weather.climatology(s.lat, s.lon)
    df = build_rows(daily, meta, temps, clim, cycle_days=s.cycle_days, step=a.step)
    out = DATA / "features.parquet"
    df.to_parquet(out, index=False)
    asset = export_train_asset(df)
    _print({"rows": len(df), "houses": int(df["house"].nunique()), "windows": int(df.groupby(["house", "cycle_start"]).ngroups),
            "ratio_median": round(float(df["ratio"].median()), 4), "features": str(out), "train_asset": str(asset)})
    return 0


def cmd_backtest(a: argparse.Namespace) -> int:
    from slabwatch.evaluate import run_backtest

    _print(run_backtest(a.models.split(","), weather=a.weather, folds=a.folds, sample=a.sample))
    return 0


def _parse_readings(items: list[str]) -> list[dict]:
    out = []
    for it in items:
        date, _, val = it.partition("=")
        out.append({"date": date, "reading_kwh": float(val)})
    return out


def cmd_forecast(a: argparse.Namespace) -> int:
    from slabwatch.service import forecast_cycle

    out = forecast_cycle(a.cycle_start, a.start_reading, _parse_readings(a.reading), a.threshold,
                         a.cycle_days, None, a.prev_units, a.backend)
    if a.json:
        _print(out)
    else:
        f, d = out["forecast"], out["decision"]
        print(f"[{d['verdict']}] {d['message']}\n  {d['message_ur']}")
        print(f"  P10 {f['p10']:.0f} | P50 {f['p50']:.0f} | P90 {f['p90']:.0f} | P(>{f['threshold']:g}) "
              f"{f['p_cross']:.0%} | backend {f['backend']}")
    return 0


def cmd_add_reading(a: argparse.Namespace) -> int:
    import datetime as dt

    from slabwatch import store

    value, src, conf, label = a.kwh, "manual", None, None
    if a.photo:
        from slabwatch.gemma import read_meter

        r = read_meter(Path(a.photo))
        _print(r)
        if r["reading_kwh"] is None:
            print("Not stored: the photo was not readable. Pass --kwh instead.", file=sys.stderr)
            return 2
        value, src, conf, label = r["reading_kwh"], "photo", r["confidence"], r["display_label"]
    if value is None:
        print("pass --kwh or --photo", file=sys.stderr)
        return 2
    ts = dt.datetime.combine(dt.date.fromisoformat(a.date), dt.time(12), dt.timezone(dt.timedelta(hours=5)))
    store.add_reading(a.household, ts, value, src, conf, label)
    print(f"stored {value} kWh for {a.household} on {a.date}")
    if a.signal:
        from slabwatch.workflows import signal_reading

        asyncio.run(signal_reading(a.household, value, a.date, src))
        print("signalled workflow")
    return 0


def cmd_serve(a: argparse.Namespace) -> int:
    from slabwatch.web import serve

    serve(a.host, a.port)
    return 0


def cmd_worker(a: argparse.Namespace) -> int:
    from slabwatch.worker import run_worker

    asyncio.run(run_worker())
    return 0


def cmd_start_cycle(a: argparse.Namespace) -> int:
    from slabwatch.workflows import start_cycle

    print(asyncio.run(start_cycle(a.household, a.cycle_start, a.cycle_days)))
    return 0


def cmd_db_init(a: argparse.Namespace) -> int:
    from slabwatch import store

    _print(store.init_db())
    return 0


def cmd_fetch_bill(a: argparse.Namespace) -> int:
    from slabwatch import bill

    if a.text_file:
        _print(bill.parse_bill(Path(a.text_file).read_text(), use_gemma=not a.no_gemma))
        return 0
    if a.photo:
        from slabwatch.gemma import read_bill_image

        _print(read_bill_image(Path(a.photo)))
        return 0
    got = bill.fetch_bill(a.ref, a.disco)
    text = got.pop("text", "")
    _print(got)
    if got.get("ok"):
        _print(bill.parse_bill(text, use_gemma=not a.no_gemma))
    return 0 if got.get("ok") else 1


def cmd_tariff_watch(a: argparse.Namespace) -> int:
    from slabwatch import tariff

    if a.search:
        from slabwatch import store

        _print(store.search_tariff(a.search))
        return 0
    _print(tariff.watch(store_db=not a.no_db))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="slabwatch",
                                description="Forecast this billing cycle's electricity units before the 200-unit cliff.")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="check keys, imports, data; optionally ping one service")
    d.add_argument("--ping", choices=["weather", "tiger", "gemma", "ntfy", "browserbase", "tabpfn", "temporal"])
    d.set_defaults(fn=cmd_doctor)

    f = sub.add_parser("fetch-data", help="download + extract PRECON from Open Data Pakistan, aggregate to daily kWh")
    f.add_argument("--houses", default="1-10", choices=["1-10", "11-20", "21-31", "31-42", "all"])
    f.set_defaults(fn=cmd_fetch_data)

    b = sub.add_parser("build-features", help="daily kWh + Open-Meteo archive -> data/features.parquet")
    b.add_argument("--step", type=int, default=15, help="slide between 30-day windows (days)")
    b.set_defaults(fn=cmd_build_features)

    bt = sub.add_parser("backtest", help="GroupKFold-by-house backtest -> docs/RESULTS.md + results/*.json")
    bt.add_argument("--models", default="naive,last_ratio,gbm",
                    help="comma list of naive,last_ratio,gbm,tabpfn_local,tabpfn_api")
    bt.add_argument("--weather", default="actual", choices=["actual", "clim"])
    bt.add_argument("--folds", type=int, default=5)
    bt.add_argument("--sample", type=int, default=0, help="cap training rows per fold for TabPFN (<=5000 on CPU)")
    bt.set_defaults(fn=cmd_backtest)

    fc = sub.add_parser("forecast", help="forecast one cycle from meter readings")
    fc.add_argument("--cycle-start", required=True); fc.add_argument("--start-reading", type=float, required=True)
    fc.add_argument("--reading", action="append", required=True, metavar="YYYY-MM-DD=KWH")
    fc.add_argument("--threshold", type=float); fc.add_argument("--cycle-days", type=int)
    fc.add_argument("--prev-units", type=float, help="last bill's units (optional feature)")
    fc.add_argument("--backend"); fc.add_argument("--json", action="store_true")
    fc.set_defaults(fn=cmd_forecast)

    ar = sub.add_parser("add-reading", help="store a meter reading (typed or from a photo) in Postgres")
    ar.add_argument("--household", required=True); ar.add_argument("--date", required=True)
    ar.add_argument("--kwh", type=float); ar.add_argument("--photo")
    ar.add_argument("--signal", action="store_true", help="also signal the Temporal cycle workflow")
    ar.set_defaults(fn=cmd_add_reading)

    sv = sub.add_parser("serve", help="run the web app (uvicorn)")
    sv.add_argument("--host", default="0.0.0.0"); sv.add_argument("--port", type=int, default=8000)
    sv.set_defaults(fn=cmd_serve)

    sub.add_parser("worker", help="run the Temporal worker").set_defaults(fn=cmd_worker)

    sc = sub.add_parser("start-cycle", help="start a household's CycleWorkflow")
    sc.add_argument("--household", required=True); sc.add_argument("--cycle-start", required=True)
    sc.add_argument("--cycle-days", type=int, default=30)
    sc.set_defaults(fn=cmd_start_cycle)

    sub.add_parser("db-init", help="create tables (+hypertables, +pgvector if available)").set_defaults(fn=cmd_db_init)

    fb = sub.add_parser("fetch-bill", help="PITC duplicate bill via Browserbase (or parse a saved text / photo)")
    fb.add_argument("--ref", help="14-digit reference number"); fb.add_argument("--disco", default="lesco")
    fb.add_argument("--text-file"); fb.add_argument("--photo"); fb.add_argument("--no-gemma", action="store_true")
    fb.set_defaults(fn=cmd_fetch_bill)

    tw = sub.add_parser("tariff-watch", help="Browserbase search + page read for this month's NEPRA FCA; Gemma extracts; store + hybrid search")
    tw.add_argument("--search", help="query stored docs instead (hybrid RRF if embeddings exist)")
    tw.add_argument("--no-db", action="store_true")
    tw.set_defaults(fn=cmd_tariff_watch)
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd == "fetch-bill" and not (a.ref or a.text_file or a.photo):
        print("fetch-bill needs --ref, --text-file or --photo", file=sys.stderr)
        return 2
    try:
        return a.fn(a)
    except Exception as e:  # noqa: BLE001 — print a clean message, not a traceback, for known failures
        from slabwatch.config import MissingKey

        if isinstance(e, (MissingKey, RuntimeError, ValueError, FileNotFoundError)):
            print(f"error: {e}", file=sys.stderr)
            return 1
        raise
