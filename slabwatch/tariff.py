"""Tariff watcher: finds this month's fuel charges adjustment (FCA) news and lets Gemma read it.

Browserbase does both web jobs. Search finds candidate articles, and one cloud-browser session opens
them and pulls the page text that Gemma reasons over. Gemma only extracts; code checks that the
sentence it quotes is really on the page and contains the number, and refuses otherwise.

Why not the official sources: from Browserbase's (US) IPs, nepra.org.pk answers with a Cloudflare 403
and the PITC/LESCO sites time out (checked 2026-10-24). Pakistani business news (brecorder.com,
tribune.com.pk) loads fine, and it reports every NEPRA FCA decision.

The forecast is in units; rupees are an estimate, so the page must say which adjustment it assumed.
"""
from __future__ import annotations

import datetime as dt
import json
import re

from slabwatch.config import RESULTS, Settings, settings

MAX_CHARS = 3500      # page text handed to Gemma per article (a window around the first FCA mention)
FCA_WORDS = re.compile(r"fuel (?:charges? |cost |price )?adjustment|\bFCA\b|\bFPA\b|per unit", re.I)
NEWS_HINT = re.compile(r"brecorder|tribune|dawn|thenews|geo\.tv|propakistani|nation\.com\.pk|app\.com\.pk")

FCA_SCHEMA = {
    "type": "object",
    "properties": {
        "fca_rs_per_unit": {"type": ["number", "null"]},
        "direction": {"type": ["string", "null"]},
        "reference_month": {"type": ["string", "null"]},
        "billing_month": {"type": ["string", "null"]},
        "applies_to": {"type": ["string", "null"]},
        "quote": {"type": ["string", "null"]},
    },
    "required": ["fca_rs_per_unit", "quote"],
}

FCA_PROMPT = """You read Pakistani electricity news. From the ARTICLE below, extract the NEPRA fuel charges
adjustment (FCA, also called FPA) for ex-WAPDA distribution companies (DISCOs).

Return ONLY a JSON object:
{"fca_rs_per_unit": number or null, "direction": "increase" or "decrease" or null,
 "reference_month": "Month YYYY" or null (the month whose fuel cost it adjusts),
 "billing_month": "Month YYYY" or null (the bills it is charged on),
 "applies_to": short text or null (e.g. "DISCOs except K-Electric"),
 "quote": the exact sentence from the article that states the number, copied character for character}

If the article does not state an FCA number for DISCOs, return {"fca_rs_per_unit": null, "quote": null}.
Never compute or guess a number.

ARTICLE:
"""


def queries(month: dt.date | None = None) -> list[str]:
    m = month or dt.date.today()
    return [f"NEPRA fuel charges adjustment {m:%B} {m.year} DISCOs per unit",
            f"NEPRA FCA {m:%B} {m.year}"]


def _client(s: Settings):
    key = s.require("browserbase_api_key", "BROWSERBASE_API_KEY", "tariff watch")
    from browserbase import Browserbase

    return Browserbase(api_key=key)


def search(q: str, s: Settings | None = None, num: int = 8) -> list[dict]:
    """Browserbase Search. Returns [{url, title, published, query}]."""
    s = s or settings()
    r = _client(s).search.web(query=q, num_results=num)
    return [{"url": it.url, "title": it.title,
             "published": it.published_date.isoformat() if it.published_date else None, "query": q}
            for it in r.results if it.url]


def read_pages(urls: list[str], s: Settings | None = None) -> tuple[list[dict], str]:
    """Open each URL in one Browserbase session; return [{url, text}] and the session replay link."""
    s = s or settings()
    from playwright.sync_api import sync_playwright

    session = _client(s).sessions.create()
    replay = f"https://www.browserbase.com/sessions/{session.id}"
    out = []
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(session.connect_url)
        try:
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            for url in urls:
                try:
                    r = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    art = page.locator("article")
                    text = art.first.inner_text() if art.count() else page.inner_text("body")
                    out.append({"url": url, "status": r.status if r else None, "title": page.title(),
                                "text": re.sub(r"\s+", " ", text).strip()})
                except Exception as e:  # noqa: BLE001 - one bad page must not stop the rest
                    out.append({"url": url, "status": None, "error": str(e).splitlines()[0][:160]})
        finally:
            browser.close()
    return out, replay


def _norm(t: str) -> str:
    return re.sub(r"[\s’‘'\"`]+", " ", t).strip().lower()


def number_in(val: float, quote: str) -> bool:
    """Does the quote state this number (e.g. 1.25 as '1.25', 0.5 as '0.50' or '50 paisa')?"""
    nums = [float(x.replace(",", "")) for x in re.findall(r"\d+(?:[.,]\d+)?", quote)]
    paisa = [n / 100 for n in nums] if re.search(r"paisa|paise", quote, re.I) else []
    return any(abs(n - abs(val)) < 1e-6 for n in nums + paisa)


def window(text: str) -> str:
    """The part of the page Gemma needs: from a little before the first FCA mention."""
    m = FCA_WORDS.search(text)
    start = max(0, (m.start() if m else 0) - 300)
    return text[start:start + MAX_CHARS]


def extract_fca(text: str, s: Settings | None = None) -> dict:
    """Gemma reads one article. Refuses unless the quoted sentence is on the page and holds the number."""
    from slabwatch.gemma import Refused, _ask

    text = window(text)
    try:
        got = _ask(FCA_PROMPT + text, None, "text/plain", FCA_SCHEMA, s)
    except Refused as e:
        return {"fca_rs_per_unit": None, "refused": str(e)}
    except Exception as e:  # noqa: BLE001 - a timeout on one article is not fatal
        return {"fca_rs_per_unit": None, "refused": f"Gemma call failed: {str(e)[:160]}"}
    val, quote = got.get("fca_rs_per_unit"), got.get("quote")
    if val is None:
        return {"fca_rs_per_unit": None, "refused": "article states no DISCO FCA"}
    if not quote or _norm(quote) not in _norm(text):
        return {"fca_rs_per_unit": None, "refused": "quoted sentence not found on the page", "quote": quote}
    if not number_in(float(val), quote):
        return {"fca_rs_per_unit": None, "refused": f"number {val} not in the quoted sentence", "quote": quote}
    if not 0 < abs(float(val)) < 15:
        return {"fca_rs_per_unit": None, "refused": f"{val} Rs/unit is outside any recent FCA"}
    return {**got, "fca_rs_per_unit": float(val), "refused": None}


def watch(month: dt.date | None = None, store_db: bool = True, max_pages: int = 4) -> dict:
    """Search, open the most news-like results, let Gemma extract, log under results/tariff/, store."""
    s = settings()
    found, log = [], []
    for q in queries(month):
        got = search(q, s)
        log.append({"q": q, "n": len(got)})
        found += got
    seen, uniq = set(), []
    for d in sorted(found, key=lambda d: not NEWS_HINT.search(d["url"])):  # news sites first
        if d["url"] not in seen:
            seen.add(d["url"])
            uniq.append(d)
    pages, replay = read_pages([d["url"] for d in uniq[:max_pages]], s) if uniq else ([], None)
    meta = {d["url"]: d for d in uniq}
    docs = []
    for p in pages:
        d = {**meta.get(p["url"], {}), **p}
        if p.get("text"):
            d["fca"] = extract_fca(p["text"], s)
            d["snippet"] = d["fca"].get("quote") or p["text"][:300]
        docs.append(d)
    best = next((d for d in docs if (d.get("fca") or {}).get("fca_rs_per_unit") is not None), None)
    out_dir = RESULTS / "tariff"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"browserbase-{dt.datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps({"log": log, "replay": replay,
                                "docs": [{k: v for k, v in d.items() if k != "text"} for d in docs]},
                               indent=2, ensure_ascii=False, default=str))
    stored = None
    if store_db and s.database_url:
        from slabwatch import store

        stored = store.save_tariff_docs([{**d, "source": "browserbase"} for d in docs if d.get("text")])
    return {"queries": log, "opened": len(pages), "replay": replay, "log_file": str(path), "stored": stored,
            "fca": best["fca"] if best else None, "fca_source": best["url"] if best else None}
