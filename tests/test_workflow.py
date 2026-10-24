"""CycleWorkflow on Temporal's time-skipping test server with stub activities.

Skipped automatically if temporalio is missing or the test server can't be downloaded (offline)."""
import asyncio
import datetime as dt
import uuid

import pytest

temporalio = pytest.importorskip("temporalio")
from temporalio import activity  # noqa: E402
from temporalio.testing import WorkflowEnvironment  # noqa: E402
from temporalio.worker import Worker  # noqa: E402

from slabwatch.workflows import CycleInput, CycleWorkflow, ForecastResult, ReadingSignal  # noqa: E402

calls: list = []
VERDICTS = iter(["safe", "act", "act", "already_over", "already_over"])


@activity.defn(name="nudge_activity")
async def nudge(hid: str, day: int) -> str:
    calls.append(("nudge", day))
    return "ok"


@activity.defn(name="forecast_activity")
async def fc(hid: str, start: str, days: int) -> ForecastResult:
    v = next(VERDICTS)
    calls.append(("forecast", v))
    return ForecastResult(v, f"msg {v}", 200.0, 0.5)


@activity.defn(name="alert_activity")
async def alert(hid: str, msg: str) -> None:
    calls.append(("alert", msg))


@activity.defn(name="bill_and_score_activity")
async def bill(hid: str, start: str) -> dict:
    calls.append(("bill", start))
    return {"scored": True}


def test_cycle_workflow_timers_signals_and_single_alerts():
    async def main():
        try:
            env = await asyncio.wait_for(WorkflowEnvironment.start_time_skipping(), 120)
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"temporal test server unavailable: {e}")
        async with env:
            q = f"q-{uuid.uuid4()}"
            async with Worker(env.client, task_queue=q, workflows=[CycleWorkflow],
                              activities=[nudge, fc, alert, bill]):
                start = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).date().isoformat()
                h = await env.client.start_workflow(CycleWorkflow.run, CycleInput("h1", start, 30, [5, 10, 15, 20, 25], 36, 3),
                                                    id=f"wf-{uuid.uuid4()}", task_queue=q)
                # Send a reading each time the workflow is waiting for one (skipping time in between).
                for _ in range(5):
                    for _ in range(200):
                        st = await h.query(CycleWorkflow.status)
                        if st["phase"].startswith("waiting for reading"):
                            break
                        await env.sleep(dt.timedelta(hours=6))
                    await h.signal(CycleWorkflow.reading_added, ReadingSignal(100.0, start))
                    await env.sleep(dt.timedelta(minutes=1))
                for _ in range(200):
                    if any(c[0] == "bill" for c in calls):
                        break
                    await env.sleep(dt.timedelta(hours=12))

    asyncio.run(main())
    kinds = [c[0] for c in calls]
    assert kinds.count("nudge") == 5 and kinds.count("forecast") == 5
    alerts = [c for c in calls if c[0] == "alert"]
    assert [a[1] for a in alerts] == ["msg act", "msg already_over"]   # once per escalation
    assert "bill" in kinds and kinds.index("bill") > max(i for i, k in enumerate(kinds) if k == "forecast")
