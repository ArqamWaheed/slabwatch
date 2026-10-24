"""SerpApi watcher for this month's fuel charges adjustment (FCA / FPA) news from NEPRA.

The forecast is in units; rupees are an estimate, so the page must say which adjustment it assumed.
"""
from __future__ import annotations

import datetime as dt
import json

from slabwatch.config import RESULTS, Settings, settings
from slabwatch.net import get_json

SERPAPI = "https://serpapi.com/search.json"


def queries(month: dt.date | None = None) -> list[str]:
    m = month or dt.date.today()
    return [f"NEPRA fuel charges adjustment {m:%B} {m.year}",
            f"NEPRA FCA {m:%B} {m.year} DISCOs per unit",
            "protected consumers 200 units NEPRA notification"]


def search(q: str, engine: str = "google", s: Settings | None = None, num: int = 10) -> list[dict]:
    s = s or settings()
    key = s.require("serpapi_key", "SERPAPI_KEY", "tariff watch")
    params = {"engine": engine, "q": q, "api_key": key, "gl": "pk", "hl": "en"}
    if engine == "google":
        params["num"] = num
    r = get_json(SERPAPI, params, timeout=60)
    items = r.get("news_results") or r.get("organic_results") or []
    out = []
    for it in items[:num]:
        link = it.get("link")
        if not link:
            continue
        out.append({"url": link, "title": it.get("title"), "snippet": it.get("snippet"),
                    "published": it.get("date"),
                    "source": (it.get("source") or {}).get("name") if isinstance(it.get("source"), dict)
                    else it.get("source"), "query": q, "engine": engine})
    return out


def watch(month: dt.date | None = None, store_db: bool = True) -> dict:
    """Run the queries (web + news), log them under results/tariff/, and store into tariff_docs if possible."""
    s = settings()
    docs, log = [], []
    for q in queries(month):
        for engine in ("google", "google_news"):
            got = search(q, engine, s)
            log.append({"q": q, "engine": engine, "n": len(got)})
            docs += got
    seen, uniq = set(), []
    for d in docs:
        if d["url"] not in seen:
            seen.add(d["url"])
            uniq.append(d)
    out_dir = RESULTS / "tariff"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"serpapi-{dt.datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps({"log": log, "docs": uniq}, indent=2, ensure_ascii=False))
    stored = None
    if store_db and s.database_url:
        from slabwatch import store

        stored = store.save_tariff_docs(uniq)
    return {"queries": log, "docs": len(uniq), "stored": stored, "log_file": str(path)}
