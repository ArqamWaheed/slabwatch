from fastapi.testclient import TestClient

from slabwatch.web import app

c = TestClient(app)


def test_healthz_is_fast_and_local():
    r = c.get("/healthz")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_index_served():
    assert "Slabwatch" in c.get("/").text


def test_forecast_validates_input():
    assert c.post("/api/forecast", json={"cycle_start": "2026-10-01", "start_reading": 100, "readings": []}).status_code == 422


def test_forecast_rejects_meter_going_backwards():
    r = c.post("/api/forecast", json={"cycle_start": "2026-10-01", "start_reading": 500,
                                      "readings": [{"date": "2026-10-10", "reading_kwh": 400}]})
    assert r.status_code == 400


def test_static_tokens_and_mark_served():
    assert "--casing" in c.get("/static/tokens.css").text
    assert c.get("/static/mark.svg").status_code == 200
