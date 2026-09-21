"""Periodic jobs that run inside the API process.

Decision D4 (Inngest vs Celery vs APScheduler) is still open, so this is
the same shape as `modules/intelligence/worker.py`: a plain asyncio loop
that calls small, runtime-agnostic functions. Replacing it with a hosted
scheduler means each registered function becomes a handler body — nothing
inside the functions changes.

Every job is written to be safe to run twice and safe to skip a tick:
settlement is idempotent, expiry is a state check, reconciliation re-reads
provider truth. A job that raises is logged and retried next tick; it never
takes the loop or the API down.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI

from .config import get_settings
from .startup import assert_safe_to_start

logger = logging.getLogger("clippit.jobs")


@dataclass(frozen=True)
class Job:
    name: str
    interval_seconds: float
    run: Callable[[], Awaitable[None]]


_JOBS: list[Job] = []


def register(name: str, interval_seconds: float, run: Callable[[], Awaitable[None]]) -> None:
    if any(job.name == name for job in _JOBS):
        return
    _JOBS.append(Job(name=name, interval_seconds=interval_seconds, run=run))


def registered() -> list[Job]:
    return list(_JOBS)


async def _loop(job: Job) -> None:
    while True:
        try:
            await job.run()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — a bad tick must not end the loop
            logger.exception("job %s failed; will retry in %ss", job.name, job.interval_seconds)
        await asyncio.sleep(job.interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    assert_safe_to_start()
    tasks: list[asyncio.Task] = []
    if get_settings().background_jobs_enabled:
        for job in _JOBS:
            tasks.append(asyncio.create_task(_loop(job), name=f"job:{job.name}"))
        logger.info("started %d background job(s): %s", len(tasks), ", ".join(j.name for j in _JOBS))
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
