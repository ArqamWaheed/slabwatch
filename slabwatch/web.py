"""FastAPI app (Render free web service). /healthz never calls anything external."""
from __future__ import annotations

import datetime as dt
import threading
from importlib import resources

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from slabwatch import __version__
from slabwatch.config import MissingKey, settings

app = FastAPI(title="Slabwatch", version=__version__)
_BOOT = dt.datetime.now(dt.timezone.utc)
_warm = {"state": "cold", "error": None}
app.mount("/static", StaticFiles(directory=str(resources.files("slabwatch").joinpath("static"))), name="static")


class Reading(BaseModel):
    date: str
    reading_kwh: float = Field(ge=0)


class ForecastIn(BaseModel):
    cycle_start: str
    start_reading: float = Field(ge=0)
    readings: list[Reading] = Field(min_length=1)
    threshold: float | None = Field(default=None, gt=0)
    cycle_days: int | None = Field(default=None, ge=20, le=40)
    prev_cycle_units: float | None = Field(default=None, ge=0)
    sanctioned_kw: float = Field(default=2.0, gt=0, le=50)
    meta: dict[str, float] | None = None


class ReadingIn(Reading):
    household_id: str = Field(min_length=1, max_length=64)
    source: str = "manual"


def _error(e: Exception) -> HTTPException:
    if isinstance(e, MissingKey):
        return HTTPException(503, str(e))
    if isinstance(e, ValueError):
        return HTTPException(400, str(e))
    return HTTPException(502, f"{type(e).__name__}: {e}")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "version": __version__, "up_since": _BOOT.isoformat(), "model": _warm["state"]}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return resources.files("slabwatch").joinpath("static/index.html").read_text()


@app.get("/api/config")
def config() -> dict:
    s = settings()
    return {"threshold": s.slab_threshold, "penalty_months": s.penalty_months, "cycle_days": s.cycle_days,
            "backend": s.forecast_backend, "gemma": s.gemma_provider,
            "photo_enabled": bool(s.google_api_key) or s.gemma_provider == "ollama", "model": _warm}


def _fit() -> None:
    from slabwatch.service import model

    _warm["state"] = "warming"
    try:
        model()
        _warm["state"] = "ready"
    except Exception as e:  # noqa: BLE001
        _warm.update(state="error", error=str(e))


@app.post("/api/warm")
def warm() -> dict:
    """Fit the model in the background after a cold start, so the first forecast is quick."""
    if _warm["state"] in ("cold", "error"):
        threading.Thread(target=_fit, daemon=True).start()
        _warm["state"] = "warming"
    return _warm


@app.post("/api/forecast")
def forecast(body: ForecastIn) -> dict:
    from slabwatch.service import forecast_cycle

    try:
        out = forecast_cycle(body.cycle_start, body.start_reading, [r.model_dump() for r in body.readings],
                             body.threshold, body.cycle_days, body.meta, body.prev_cycle_units,
                             sanctioned_kw=body.sanctioned_kw)
        _warm["state"] = "ready"
        return out
    except Exception as e:  # noqa: BLE001
        raise _error(e) from None


@app.post("/api/reading")
def add_reading(body: ReadingIn) -> dict:
    """Store a reading (needs DATABASE_URL) and wake the household's Temporal workflow if one runs."""
    from slabwatch import store

    try:
        ts = dt.datetime.combine(dt.date.fromisoformat(body.date), dt.time(12), dt.timezone(dt.timedelta(hours=5)))
        store.add_reading(body.household_id, ts, body.reading_kwh, body.source)
    except Exception as e:  # noqa: BLE001
        raise _error(e) from None
    signalled = False
    if settings().temporal_address:
        try:
            import asyncio

            from slabwatch.workflows import signal_reading

            asyncio.run(signal_reading(body.household_id, body.reading_kwh, body.date, body.source))
            signalled = True
        except Exception:  # noqa: BLE001 — no worker / no workflow is fine
            signalled = False
    return {"stored": True, "signalled_workflow": signalled}


MAX_PHOTO = 8 * 1024 * 1024


@app.post("/api/photo")
async def photo(file: UploadFile = File(...)) -> JSONResponse:
    from slabwatch.gemma import read_meter

    data = await file.read()
    if not data or len(data) > MAX_PHOTO:
        raise HTTPException(400, "photo must be between 1 byte and 8 MB")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "upload an image")
    try:
        return JSONResponse(read_meter(data, file.content_type))
    except Exception as e:  # noqa: BLE001
        raise _error(e) from None


@app.post("/api/bill-photo")
async def bill_photo(file: UploadFile = File(...)) -> JSONResponse:
    """Gemma reads the usage history off a photo of the paper bill. Only months/units/amounts are returned;
    the reference number is dropped so it never reaches the page."""
    from slabwatch.gemma import read_bill_image

    data = await file.read()
    if not data or len(data) > MAX_PHOTO:
        raise HTTPException(400, "photo must be between 1 byte and 8 MB")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "upload an image")
    try:
        got = read_bill_image(data, mime=file.content_type)
    except Exception as e:  # noqa: BLE001
        raise _error(e) from None
    return JSONResponse({"current_units": got.get("current_units"), "history": got.get("history", [])})


def serve(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)
