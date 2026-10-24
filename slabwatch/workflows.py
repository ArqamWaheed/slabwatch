"""Temporal: one durable CycleWorkflow per household per billing cycle.

  day 5,10,15,20,25 (09:00 PKT): nudge for a meter photo (ntfy) -> wait for `reading_added` (36 h max)
                                 -> re-forecast -> alert ONLY if the verdict escalated to act/already_over
  cycle end + 3 days:            fetch the real bill, score our last forecast, continue_as_new(next cycle)

Workflow code is deterministic: no I/O, no datetime.now(), no random. Time comes from workflow.now(),
waiting from workflow.sleep()/wait_condition(); everything else is an activity.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass, field

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from slabwatch.decide import escalated

PKT = dt.timezone(dt.timedelta(hours=5))
NUDGE_HOUR = 9


@dataclass
class CycleInput:
    household_id: str
    cycle_start: str                      # YYYY-MM-DD (day the meter was read for the last bill)
    cycle_days: int = 30
    reading_days: list[int] = field(default_factory=lambda: [5, 10, 15, 20, 25])
    reading_wait_hours: int = 36
    bill_lag_days: int = 3
    cycles_run: int = 0


@dataclass
class ReadingSignal:
    reading_kwh: float
    date: str
    source: str = "photo"


@dataclass
class ForecastResult:
    verdict: str
    message: str
    p50: float | None = None
    p_cross: float | None = None
    error: str | None = None


# ---------------------------------------------------------------- activities (all I/O lives here)
@activity.defn
async def nudge_activity(household_id: str, day: int) -> str:
    from slabwatch.service import notify

    msg = f"Day {day} of your billing cycle: please send a meter photo (about 20 seconds)."
    await asyncio.to_thread(notify, msg, "Slabwatch: meter photo")
    return msg


@activity.defn
async def forecast_activity(household_id: str, cycle_start: str, cycle_days: int) -> ForecastResult:
    from slabwatch import store
    from slabwatch.service import forecast_cycle

    def run() -> ForecastResult:
        start = dt.date.fromisoformat(cycle_start)
        rows = store.readings(household_id, dt.datetime.combine(start, dt.time(), PKT) - dt.timedelta(days=3))
        if not rows:
            return ForecastResult("none", "no readings yet", error="no readings")
        # The reading closest to the cycle start is the baseline (from the bill or the first photo).
        base = min(rows, key=lambda r: abs((r[0].date() - start).days))
        rs = [{"date": r[0].date().isoformat(), "reading_kwh": r[1]} for r in rows if r[0].date() > start]
        if not rs:
            return ForecastResult("none", "only the baseline reading so far", error="no in-cycle readings")
        out = forecast_cycle(start, base[1], rs, cycle_days=cycle_days)
        f, d = out["forecast"], out["decision"]
        store.save_forecast(household_id, start, f, d)
        return ForecastResult(d["verdict"], d["message"], f["p50"], f["p_cross"])

    return await asyncio.to_thread(run)


@activity.defn
async def alert_activity(household_id: str, message: str) -> None:
    from slabwatch.service import notify

    await asyncio.to_thread(notify, message, "Slabwatch: units check", "high")


@activity.defn
async def bill_and_score_activity(household_id: str, cycle_start: str) -> dict:
    """Fetch the bill (Browserbase), store history, and score the last forecast of this cycle."""
    from slabwatch import bill, store

    def run() -> dict:
        with store.connect() as c:
            row = c.execute("SELECT reference_no, disco FROM households WHERE id=%s", (household_id,)).fetchone()
        if not row or not row[0]:
            return {"scored": False, "reason": "no reference number saved; upload a bill photo instead"}
        got = bill.fetch_bill(row[0], row[1] or "lesco")
        if not got.get("ok"):
            return {"scored": False, "reason": got.get("reason"), "replay": got.get("replay")}
        parsed = bill.parse_bill(got["text"])
        store.save_cycles_from_history(household_id, parsed["history"])
        billed = parsed.get("current_units") or (parsed["history"][-1]["units"] if parsed["history"] else None)
        if billed is None:
            return {"scored": False, "reason": "bill had no units"}
        with store.connect() as c:
            c.execute("UPDATE forecasts SET scored_error = %s - p50 WHERE household_id=%s AND cycle_start=%s",
                      (billed, household_id, cycle_start))
        return {"scored": True, "billed_units": billed, "replay": got.get("replay")}

    return await asyncio.to_thread(run)


ACTIVITIES = [nudge_activity, forecast_activity, alert_activity, bill_and_score_activity]
_RETRY = RetryPolicy(maximum_attempts=3, initial_interval=dt.timedelta(seconds=10))


# ---------------------------------------------------------------- workflow
@workflow.defn
class CycleWorkflow:
    def __init__(self) -> None:
        self._readings: list[ReadingSignal] = []
        self._fresh = False
        self._last_verdict: str | None = None
        self._alerted: str | None = None
        self._phase = "starting"

    @workflow.signal
    def reading_added(self, r: ReadingSignal) -> None:
        self._readings.append(r)
        self._fresh = True

    @workflow.query
    def status(self) -> dict:
        return {"phase": self._phase, "readings": len(self._readings),
                "last_verdict": self._last_verdict, "alerted": self._alerted}

    async def _sleep_until(self, when: dt.datetime) -> None:
        delay = when - workflow.now()
        if delay > dt.timedelta(0):
            await workflow.sleep(delay)

    async def _forecast(self, inp: CycleInput) -> None:
        res: ForecastResult = await workflow.execute_activity(
            forecast_activity, args=[inp.household_id, inp.cycle_start, inp.cycle_days],
            start_to_close_timeout=dt.timedelta(minutes=5), retry_policy=_RETRY)
        if res.error:
            return
        self._last_verdict = res.verdict
        if escalated(self._alerted, res.verdict):
            await workflow.execute_activity(alert_activity, args=[inp.household_id, res.message],
                                            start_to_close_timeout=dt.timedelta(seconds=60),
                                            retry_policy=_RETRY)
            self._alerted = res.verdict

    @workflow.run
    async def run(self, inp: CycleInput) -> dict:
        start = dt.datetime.combine(dt.date.fromisoformat(inp.cycle_start), dt.time(NUDGE_HOUR), PKT)
        for day in inp.reading_days:
            self._phase = f"sleeping until day {day}"
            await self._sleep_until(start + dt.timedelta(days=day))
            if not self._fresh:  # a reading may already have arrived on its own
                self._phase = f"nudging day {day}"
                await workflow.execute_activity(nudge_activity, args=[inp.household_id, day],
                                                start_to_close_timeout=dt.timedelta(seconds=60),
                                                retry_policy=_RETRY)
                self._phase = f"waiting for reading (day {day})"
                try:
                    await workflow.wait_condition(lambda: self._fresh,
                                                  timeout=dt.timedelta(hours=inp.reading_wait_hours))
                except asyncio.TimeoutError:
                    continue  # no photo this time; try again at the next reading day
            self._fresh = False
            self._phase = f"forecasting (day {day})"
            await self._forecast(inp)

        self._phase = "waiting for the bill"
        await self._sleep_until(start + dt.timedelta(days=inp.cycle_days + inp.bill_lag_days))
        score = await workflow.execute_activity(bill_and_score_activity, args=[inp.household_id, inp.cycle_start],
                                                start_to_close_timeout=dt.timedelta(minutes=5),
                                                retry_policy=RetryPolicy(maximum_attempts=2))
        nxt = (dt.date.fromisoformat(inp.cycle_start) + dt.timedelta(days=inp.cycle_days)).isoformat()
        workflow.continue_as_new(CycleInput(inp.household_id, nxt, inp.cycle_days, inp.reading_days,
                                            inp.reading_wait_hours, inp.bill_lag_days, inp.cycles_run + 1))
        return score  # unreachable; continue_as_new raises


def workflow_id(household_id: str) -> str:
    return f"slabwatch-cycle-{household_id}"


async def client():
    from temporalio.client import Client

    from slabwatch.config import settings

    s = settings()
    return await Client.connect(s.temporal_address, namespace=s.temporal_namespace)


async def start_cycle(household_id: str, cycle_start: str, cycle_days: int = 30) -> str:
    from slabwatch.config import settings

    c = await client()
    h = await c.start_workflow(CycleWorkflow.run, CycleInput(household_id, cycle_start, cycle_days),
                               id=workflow_id(household_id), task_queue=settings().temporal_queue)
    return h.id


async def signal_reading(household_id: str, reading_kwh: float, date: str, source: str = "photo") -> None:
    c = await client()
    await c.get_workflow_handle(workflow_id(household_id)).signal(
        CycleWorkflow.reading_added, ReadingSignal(reading_kwh, date, source))
