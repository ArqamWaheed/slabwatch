"""Fetch the household's duplicate bill from the PITC portal through a Browserbase browser.

The portal has no API. Observed in static HTML on 2026-10-24 (https://bill.pitc.com.pk/lescobill):
  ASP.NET WebForms page; input#searchTextBox (maxlength 14, validator ^\\d{6,14}$),
  radio rbSearchByList=refno (default), select#ruCodeTextBox (urban/rural code), input#btnSearch.
  There is an empty "<!-- CAPTCHA Section -->" placeholder and `.captcha-img` CSS, so a CAPTCHA may
  appear. TO VERIFY with a real reference number: post-submit page layout, whether a CAPTCHA shows,
  and whether Browserbase's egress IPs are blocked.

Fallback: the user uploads a photo of the paper bill -> gemma.read_bill_image().
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from slabwatch.config import RESULTS, Settings, settings

PITC = "https://bill.pitc.com.pk"
DISCOS = {"lesco", "gepco", "fesco", "iesco", "mepco", "pesco", "hesco", "sepco", "qesco", "tesco"}
SEL_REF = "#searchTextBox"      # TO VERIFY after submit
SEL_SUBMIT = "#btnSearch"       # TO VERIFY after submit
SEL_CAPTCHA = ".captcha-img"    # TO VERIFY (placeholder empty on 2026-10-24)
MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def clean_ref(ref: str) -> str:
    digits = re.sub(r"\D", "", ref)
    if len(digits) != 14:
        raise ValueError("A PITC reference number has 14 digits (printed top-left on the bill).")
    return digits


def fetch_bill(ref: str, disco: str = "lesco", s: Settings | None = None, shots: Path | None = None) -> dict:
    """Open {PITC}/{disco}bill in a Browserbase session, submit the reference no, return text + screenshot."""
    s = s or settings()
    key = s.require("browserbase_api_key", "BROWSERBASE_API_KEY", "PITC bill fetch")
    disco = disco.lower().removesuffix("bill")
    if disco not in DISCOS:
        raise ValueError(f"disco must be one of {sorted(DISCOS)}")
    ref = clean_ref(ref)
    try:
        from browserbase import Browserbase
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("pip install -e .[browser]  (browserbase + playwright; no local browser needed)") from None

    bb = Browserbase(api_key=key)
    # The API key resolves the project; BROWSERBASE_PROJECT_ID is only passed if someone set it.
    session = bb.sessions.create(**({"project_id": s.browserbase_project_id} if s.browserbase_project_id else {}))
    replay = f"https://www.browserbase.com/sessions/{session.id}"
    shots = shots or (RESULTS / "bills")
    shots.mkdir(parents=True, exist_ok=True)
    shot = shots / f"{disco}-{dt.datetime.now():%Y%m%d-%H%M%S}.png"
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(session.connect_url)
        try:
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(f"{PITC}/{disco}bill", wait_until="domcontentloaded", timeout=60000)
            if page.locator(SEL_CAPTCHA).count():
                page.screenshot(path=str(shot), full_page=True)
                return {"ok": False, "reason": "captcha shown; use the bill-photo upload", "replay": replay,
                        "screenshot": str(shot)}
            page.fill(SEL_REF, ref)
            with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
                page.click(SEL_SUBMIT)
            page.wait_for_timeout(1500)
            text = page.inner_text("body")
            page.screenshot(path=str(shot), full_page=True)
        finally:
            browser.close()
    ok = bool(re.search(r"UNITS|KWH", text, re.I))
    return {"ok": ok, "reason": None if ok else "no bill found on the result page", "text": text,
            "replay": replay, "screenshot": str(shot), "url": f"{PITC}/{disco}bill"}


def parse_history_regex(text: str) -> list[dict]:
    """Regex pass over the 12-month table (MONTH UNITS BILL PAYMENT). Format TO VERIFY on a real bill.

    Accepts tokens like 'OCT25', 'Oct-25', "Oct 25" followed by units and bill amount.
    """
    out, seen = [], set()
    pat = re.compile(r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[\s\-']?(\d{2})\s+(\d{1,5})\s+(\d{1,7})\b",
                     re.I)
    for m in pat.finditer(text):
        mon = f"20{m.group(2)}-{MONTHS[m.group(1).upper()]:02d}"
        if mon in seen:
            continue
        seen.add(mon)
        out.append({"month": mon, "units": float(m.group(3)), "amount_rs": float(m.group(4))})
    return sorted(out, key=lambda h: h["month"])


def parse_bill(text: str, use_gemma: bool = True, s: Settings | None = None) -> dict:
    """Regex first (exact, cheap). If Gemma is configured, also ask it and keep rows both agree on."""
    rx = parse_history_regex(text)
    result = {"history": rx, "source": "regex", "disagreements": []}
    if not use_gemma:
        return result
    try:
        from slabwatch.gemma import read_bill_text

        g = read_bill_text(text, s)
    except Exception as e:  # noqa: BLE001 — gemma is optional here
        result["gemma_error"] = str(e)
        return result
    gm = {h["month"]: h["units"] for h in g["history"]}
    if not rx:
        return {"history": g["history"], "source": "gemma", "disagreements": [],
                "reference_no": g.get("reference_no"), "current_units": g.get("current_units")}
    result["disagreements"] = [h["month"] for h in rx if h["month"] in gm and gm[h["month"]] != h["units"]]
    result.update(source="regex+gemma", reference_no=g.get("reference_no"), current_units=g.get("current_units"))
    return result
