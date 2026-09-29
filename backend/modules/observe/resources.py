"""CPU / memory sampler for the /observe dashboard and the admin System health screen.

A small asyncio task samples every SAMPLE_SECONDS while the API runs (wrapped
around the app lifespan in `with_sampler`), so the charts have history even
when nobody has the dashboard open. In-memory only, like the rest of observe.

CPU percentages are "of one core" for the process (so a busy 2-core box can
show up to 200%) and "of the whole machine" for the host.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psutil
from fastapi import FastAPI

SAMPLE_SECONDS = 10
HISTORY = 360  # one hour

_proc = psutil.Process(os.getpid())
history: deque[dict] = deque(maxlen=HISTORY)


def _sample(loop_lag_ms: float) -> dict:
    with _proc.oneshot():
        rss = _proc.memory_info().rss
        cpu = _proc.cpu_percent(interval=None)
        threads = _proc.num_threads()
        try:
            fds = _proc.num_fds()
        except (AttributeError, psutil.Error):  # not available on Windows
            fds = None
    vm = psutil.virtual_memory()
    try:
        load1 = os.getloadavg()[0]
    except (AttributeError, OSError):
        load1 = None
    return {
        "ts": int(time.time() * 1000),
        "proc_cpu": round(cpu, 1),
        "proc_rss_mb": round(rss / 1048576, 1),
        "proc_threads": threads,
        "proc_fds": fds,
        "sys_cpu": round(psutil.cpu_percent(interval=None), 1),
        "sys_mem_pct": round(vm.percent, 1),
        "sys_mem_used_mb": round((vm.total - vm.available) / 1048576),
        "sys_mem_total_mb": round(vm.total / 1048576),
        "load1": None if load1 is None else round(load1, 2),
        "cores": psutil.cpu_count() or 1,
        "loop_lag_ms": round(loop_lag_ms, 1),
    }


async def _run() -> None:
    _proc.cpu_percent(interval=None)  # first call is meaningless; prime the counters
    psutil.cpu_percent(interval=None)
    while True:
        started = time.perf_counter()
        await asyncio.sleep(SAMPLE_SECONDS)
        # How late the loop woke us: a cheap proxy for "is the event loop blocked".
        lag = max(0.0, (time.perf_counter() - started - SAMPLE_SECONDS) * 1000)
        try:
            history.append(_sample(lag))
        except Exception:  # noqa: BLE001 — telemetry must never take the app down
            pass


def latest() -> dict:
    """Newest sample, or a fresh one-off (CPU shown as 0) if the sampler hasn't ticked yet."""
    return history[-1] if history else _sample(0.0)


def disk_percent(path: str = "/") -> float | None:
    try:
        return round(psutil.disk_usage(path).percent, 1)
    except OSError:
        return None


def with_sampler(inner):
    """Wrap an app lifespan so the sampler runs alongside it."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        from . import availability  # local: keeps this module importable without the DB layer

        tasks = [
            asyncio.create_task(_run(), name="observe:resources"),
            asyncio.create_task(availability.run(), name="observe:availability"),
        ]
        try:
            async with inner(app):
                yield
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    return lifespan
