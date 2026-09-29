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
import time
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

#: Last-run bookkeeping for the ops screens (in memory; resets on restart).
_STATUS: dict[str, dict] = {}


def status() -> list[dict]:
    """One row per registered job: cadence, last run, and whether the last run failed."""
    return [
        {"name": job.name, "interval_seconds": job.interval_seconds, **_STATUS.get(job.name, {"runs": 0, "failures": 0, "last_run_at": None, "last_ok": None, "last_error": None, "last_duration_ms": None})}
        for job in _JOBS
    ]


def register(name: str, interval_seconds: float, run: Callable[[], Awaitable[None]]) -> None:
    if any(job.name == name for job in _JOBS):
        return
    _JOBS.append(Job(name=name, interval_seconds=interval_seconds, run=run))


def registered() -> list[Job]:
    return list(_JOBS)


async def _loop(job: Job) -> None:
    while True:
        started = time.perf_counter()
        info = _STATUS.setdefault(job.name, {"runs": 0, "failures": 0, "last_run_at": None, "last_ok": None, "last_error": None, "last_duration_ms": None})
        try:
            await job.run()
            info.update(last_ok=True, last_error=None)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — a bad tick must not end the loop
            info.update(last_ok=False, last_error=type(exc).__name__, failures=info["failures"] + 1)
            logger.exception("job %s failed; will retry in %ss", job.name, job.interval_seconds)
        info.update(runs=info["runs"] + 1, last_run_at=int(time.time() * 1000), last_duration_ms=round((time.perf_counter() - started) * 1000, 1))
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
