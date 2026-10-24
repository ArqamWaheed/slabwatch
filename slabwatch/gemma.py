"""Gemma reads things; it never decides. Two jobs:
  read_meter(photo)   -> {reading_kwh, display_label, confidence, unreadable_reason}
  read_bill_text(txt) -> {reference_no, current_units, history:[{month, units, amount_rs}]}

Providers
  google: Google AI Studio REST, POST {BASE}/models/{GEMMA_MODEL}:generateContent
          (verified 2026-10-24: the key lists `gemma-4-26b-a4b-it` and `gemma-4-31b-it`;
           JSON mode (responseMimeType) works; reasoning arrives in parts marked thought=true, which are skipped).
  ollama: POST {OLLAMA_URL}/api/generate with images=[b64] and format=<JSON schema>, model gemma3:4b.

Outputs are validated strictly; anything that fails validation becomes a refusal, never a guess.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
import time
from pathlib import Path

from slabwatch.config import MissingKey, Settings, settings
from slabwatch.net import post_json

GOOGLE_BASE = "https://generativelanguage.googleapis.com/v1beta"
MIN_CONFIDENCE = 0.6

METER_SCHEMA = {
    "type": "object",
    "properties": {
        "reading_kwh": {"type": ["number", "null"]},
        "display_label": {"type": ["string", "null"]},
        "confidence": {"type": "number"},
        "unreadable_reason": {"type": ["string", "null"]},
    },
    "required": ["reading_kwh", "display_label", "confidence", "unreadable_reason"],
}
BILL_SCHEMA = {
    "type": "object",
    "properties": {
        "reference_no": {"type": ["string", "null"]},
        "current_units": {"type": ["number", "null"]},
        "history": {"type": "array", "items": {"type": "object", "properties": {
            "month": {"type": "string"}, "units": {"type": "number"},
            "amount_rs": {"type": ["number", "null"]}}, "required": ["month", "units"]}},
    },
    "required": ["reference_no", "current_units", "history"],
}

METER_PROMPT = """You are reading a photo of a Pakistani electricity meter (digital LCD that rotates
between screens, or a mechanical dial counter). Return ONLY a JSON object:
{"reading_kwh": number or null, "display_label": string or null, "confidence": 0..1,
 "unreadable_reason": string or null}
Rules:
- reading_kwh is the cumulative ACTIVE ENERGY (kWh) register only. On rotating LCDs that is the screen
  labelled kWh / "Import" / "T" (total) / code like 1.8.0. Ignore kW (demand), V, A, date and time screens.
- display_label = the code or label shown next to the number (e.g. "kWh", "1.8.0", "MDI"), else null.
- If the shown screen is not the kWh total, or digits are blurred, cut off, glared, or you are not sure
  of every digit, set reading_kwh to null and say why in unreadable_reason. Do not guess digits.
- Include decimals only if the meter shows a decimal point."""

BILL_PROMPT = """Below is the text of a Pakistani electricity bill (PITC duplicate bill). Return ONLY JSON:
{"reference_no": string or null, "current_units": number or null,
 "history": [{"month": "YYYY-MM", "units": number, "amount_rs": number or null}, ...]}
Copy numbers exactly as printed in the 12-month history table (MONTH / UNITS / BILL). If a field is
not present, use null or omit that month. Never invent months or numbers.

BILL TEXT:
"""


class Refused(ValueError):
    """Model output failed validation; caller should ask the user instead of using it."""


def _extract_json(text: str) -> dict:
    """The answer is the LAST complete JSON object. Gemma 4 on AI Studio writes its reasoning first,
    and that reasoning often restates the prompt's example objects (e.g. {"fca_rs_per_unit": null})."""
    text = text.strip()
    fences = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidates = fences[::-1]
    if not candidates:
        dec = json.JSONDecoder()
        found, i = [], text.find("{")
        while i >= 0:
            try:
                obj, end = dec.raw_decode(text, i)
                found.append(obj)
                i = text.find("{", end)
            except json.JSONDecodeError:
                i = text.find("{", i + 1)
        if not found:
            raise Refused(f"no JSON object in model output: {text[:120]!r}")
        obj = found[-1]
    else:
        try:
            obj = json.loads(candidates[0])
        except json.JSONDecodeError as e:
            raise Refused(f"invalid JSON from model: {e}") from None
    if not isinstance(obj, dict):
        raise Refused("model output is not a JSON object")
    return obj


def validate_meter(obj: dict) -> dict:
    """Strict check. Unreadable/low-confidence readings become reading_kwh=None with a reason."""
    if set(obj) - set(METER_SCHEMA["properties"]):
        obj = {k: obj[k] for k in METER_SCHEMA["properties"] if k in obj}
    for k in METER_SCHEMA["required"]:
        if k not in obj:
            raise Refused(f"missing field {k}")
    r, conf = obj["reading_kwh"], obj["confidence"]
    if r is not None and (isinstance(r, bool) or not isinstance(r, (int, float))):
        if isinstance(r, str) and re.fullmatch(r"\d+(\.\d+)?", r.strip()):
            r = float(r)
        else:
            raise Refused(f"reading_kwh is not a number: {r!r}")
    if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
        raise Refused(f"confidence out of range: {conf!r}")
    out = {"reading_kwh": float(r) if r is not None else None,
           "display_label": obj["display_label"] if isinstance(obj["display_label"], str) else None,
           "confidence": float(conf),
           "unreadable_reason": obj["unreadable_reason"] if isinstance(obj["unreadable_reason"], str) else None}
    if out["reading_kwh"] is not None and not 0 <= out["reading_kwh"] < 1e7:
        raise Refused(f"implausible reading {out['reading_kwh']}")
    if out["reading_kwh"] is None and not out["unreadable_reason"]:
        out["unreadable_reason"] = "model returned no reading"
    if out["reading_kwh"] is not None and out["confidence"] < MIN_CONFIDENCE:
        out["unreadable_reason"] = f"low confidence ({out['confidence']:.2f}); please retake or type it"
        out["reading_kwh"] = None
    return out


def check_against_previous(reading: float, prev: float | None, days: float, max_per_day: float = 150) -> str | None:
    """Plain-code sanity check. Returns a problem string or None."""
    if prev is None:
        return None
    if reading < prev:
        return f"reading {reading} is lower than the previous {prev}; meters only count up"
    if days > 0 and (reading - prev) / days > max_per_day:
        return f"{(reading - prev) / days:.0f} units/day since last reading looks wrong"
    return None


def validate_bill(obj: dict) -> dict:
    hist = obj.get("history")
    if not isinstance(hist, list):
        raise Refused("history missing")
    clean = []
    for h in hist:
        if not isinstance(h, dict) or not re.fullmatch(r"\d{4}-\d{2}", str(h.get("month", ""))):
            continue
        u = h.get("units")
        if isinstance(u, bool) or not isinstance(u, (int, float)) or not 0 <= u < 100000:
            continue
        a = h.get("amount_rs")
        clean.append({"month": h["month"], "units": float(u),
                      "amount_rs": float(a) if isinstance(a, (int, float)) and not isinstance(a, bool) else None})
    if not clean:
        raise Refused("no valid history rows")
    cu = obj.get("current_units")
    return {"reference_no": obj.get("reference_no") if isinstance(obj.get("reference_no"), str) else None,
            "current_units": float(cu) if isinstance(cu, (int, float)) and not isinstance(cu, bool) else None,
            "history": sorted(clean, key=lambda h: h["month"])}


# ---------------------------------------------------------------- providers
def _google(s: Settings, prompt: str, image: bytes | None, mime: str) -> str:
    key = s.require("google_api_key", "GOOGLE_API_KEY", "Gemma via Google AI Studio")
    parts: list[dict] = [{"text": prompt}]
    if image is not None:
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(image).decode()}})
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 4096,
                                 "responseMimeType": "application/json"}}
    from slabwatch.net import HTTPFail

    for attempt in range(4):  # the free tier answers 429 / 503 to quick back-to-back calls
        try:
            r = post_json(f"{GOOGLE_BASE}/models/{s.gemma_model}:generateContent", body, timeout=180,
                          headers={"x-goog-api-key": key})
            break
        except HTTPFail as e:
            if e.status not in (429, 500, 503) or attempt == 3:
                raise
            time.sleep(10 * (attempt + 1))
    try:
        # Gemma 4 returns its reasoning as parts marked "thought": true; only the rest is the answer.
        return "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"] if not p.get("thought"))
    except (KeyError, IndexError):
        raise Refused(f"Gemma returned no text: {str(r)[:200]}") from None


def _ollama(s: Settings, prompt: str, image: bytes | None, schema: dict) -> str:
    body = {"model": s.gemma_model, "prompt": prompt, "stream": False, "format": schema,
            "options": {"temperature": 0}}
    if image is not None:
        body["images"] = [base64.b64encode(image).decode()]
    try:
        return post_json(f"{s.ollama_url}/api/generate", body, timeout=300)["response"]
    except OSError as e:
        raise RuntimeError(f"Ollama not reachable at {s.ollama_url} ({e}). Start `ollama serve` and "
                           f"`ollama pull {s.gemma_model}`.") from None


def _ask(prompt: str, image: bytes | None, mime: str, schema: dict, s: Settings | None) -> dict:
    s = s or settings()
    if s.gemma_provider == "ollama":
        text = _ollama(s, prompt, image, schema)
    elif s.gemma_provider == "google":
        text = _google(s, prompt, image, mime)
    else:
        raise MissingKey("GEMMA_PROVIDER", "must be google or ollama")
    return _extract_json(text)


def read_meter(photo: Path | str | bytes, mime: str | None = None, s: Settings | None = None) -> dict:
    if isinstance(photo, str):
        photo = Path(photo)
    if isinstance(photo, Path):
        mime = mime or mimetypes.guess_type(photo.name)[0] or "image/jpeg"
        photo = photo.read_bytes()
    try:
        return validate_meter(_ask(METER_PROMPT, photo, mime or "image/jpeg", METER_SCHEMA, s))
    except Refused as e:
        return {"reading_kwh": None, "display_label": None, "confidence": 0.0, "unreadable_reason": str(e)}


def read_bill_text(text: str, s: Settings | None = None) -> dict:
    return validate_bill(_ask(BILL_PROMPT + text[:20000], None, "text/plain", BILL_SCHEMA, s))


def read_bill_image(photo: Path, s: Settings | None = None) -> dict:
    """Fallback when the PITC portal can't be fetched: the user uploads a photo of the bill."""
    mime = mimetypes.guess_type(photo.name)[0] or "image/jpeg"
    prompt = BILL_PROMPT.replace("Below is the text of", "This image is").replace("BILL TEXT:\n", "")
    return validate_bill(_ask(prompt, photo.read_bytes(), mime, BILL_SCHEMA, s))
