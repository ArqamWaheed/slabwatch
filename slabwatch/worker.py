"""Temporal worker entry: `python -m slabwatch worker` (or `python -m slabwatch.worker`)."""
from __future__ import annotations

import asyncio


async def run_worker() -> None:
    from temporalio.worker import Worker

    from slabwatch.config import settings
    from slabwatch.workflows import ACTIVITIES, CycleWorkflow, client

    s = settings()
    c = await client()
    print(f"worker on {s.temporal_address} queue={s.temporal_queue}")
    await Worker(c, task_queue=s.temporal_queue, workflows=[CycleWorkflow], activities=ACTIVITIES).run()


if __name__ == "__main__":
    asyncio.run(run_worker())
