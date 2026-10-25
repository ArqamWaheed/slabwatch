import datetime as dt

from slabwatch.data import weather
from slabwatch.net import HTTPFail


def test_open_meteo_429_falls_back_to_climatology(monkeypatch):
    def boom(*a, **k):
        raise HTTPFail(429, "Daily API request limit exceeded", weather.FORECAST_URL)

    monkeypatch.setattr(weather, "forecast", boom)
    monkeypatch.setattr(weather, "archive", boom)
    days = [dt.date.today() + dt.timedelta(days=i) for i in range(-10, 20)]
    notes: list[str] = []
    out = weather.temps_for(days, 31.55, 74.34, notes)  # shipped climatology asset, no network
    assert len(out) == 30 and all(v is not None for v in out.values())
    assert notes and "typical" in notes[0]
