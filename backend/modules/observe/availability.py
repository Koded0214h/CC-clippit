"""Persisted per-minute health samples → real "30-day availability".

A sample is written once a minute while the API is up and its database
answers. Availability is the share of the minutes we *expected* a sample
that have a good one — so a restart, an outage or a slow database (>2 s)
all count against it, and the figure survives deploys.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal

from .models import OpsHealthSample

logger = logging.getLogger("clippit.observe")

SAMPLE_SECONDS = 60
RETENTION_DAYS = 30
SLOW_DB_MS = 2000
MIN_HISTORY_MINUTES = 5
SERVICES = ("api", "database")


async def write_sample() -> None:
    async with AsyncSessionLocal() as db:
        started = time.perf_counter()
        await db.execute(text("SELECT 1"))
        ms = (time.perf_counter() - started) * 1000
        db.add(OpsHealthSample(service="api", ok=True, latency_ms=None))
        db.add(OpsHealthSample(service="database", ok=ms < SLOW_DB_MS, latency_ms=round(ms, 1)))
        await db.commit()


async def prune() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(OpsHealthSample).where(OpsHealthSample.ts < datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)))
        await db.commit()


async def run() -> None:
    ticks = 0
    while True:
        try:
            await write_sample()
            ticks += 1
            if ticks % 60 == 1:
                await prune()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — a missing sample IS the signal; never crash the API over it
            logger.debug("ops health sample skipped", exc_info=True)
        await asyncio.sleep(SAMPLE_SECONDS)


async def availability_30d(db: AsyncSession) -> dict[str, float | None]:
    """service -> percent over the last 30 days (or since the first sample), None if under 5 minutes of history."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=RETENTION_DAYS)
    rows = (await db.execute(
        select(
            OpsHealthSample.service,
            func.min(OpsHealthSample.ts),
            func.count().filter(OpsHealthSample.ok.is_(True)),
        ).where(OpsHealthSample.ts >= since).group_by(OpsHealthSample.service)
    )).all()
    out: dict[str, float | None] = {s: None for s in SERVICES}
    for service, first, good in rows:
        if first.tzinfo is None:
            first = first.replace(tzinfo=timezone.utc)
        expected = math.ceil((now - first).total_seconds() / SAMPLE_SECONDS) + 1
        out[service] = round(min(100.0, 100 * good / expected), 2) if expected >= MIN_HISTORY_MINUTES else None
    return out
