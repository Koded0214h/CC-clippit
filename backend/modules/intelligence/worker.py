"""The runtime that calls `run_due()` on a timer.

This file is deliberately the smallest and most disposable thing in the
module — decision D4 (Inngest vs Celery vs APScheduler) is still open, and
the whole point of keeping the scheduling logic in `scheduling.py` and the
machinery in `polling.py` is that choosing a runtime later means replacing
*this* file and nothing else. A hosted scheduler's handler body is one
line: `await coordinator.run_due()`.

Until that decision lands, a plain asyncio loop is enough to satisfy
Stage 3's exit condition — one submission growing a time series over
hours, unattended:

    python -m modules.intelligence.worker

Known limits, which are exactly why this isn't the final answer: it dies
with its process, it has no visibility beyond stdout, and a missed tick is
simply missed. The lease in `claim_due` means none of those corrupt
anything — work just waits for the next tick.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.config import get_settings
from .ingestion import IngestionService
from .polling import PollingCoordinator
from .scheduling import cadence_from_settings, tracking_window_from_settings
from .tokens import InternalApiTokenSource

logger = logging.getLogger(__name__)

DEFAULT_TICK = timedelta(seconds=60)


def build_coordinator() -> PollingCoordinator:
    token_source = InternalApiTokenSource()

    def ingestion_factory(session: AsyncSession) -> IngestionService:
        return IngestionService(session, token_source=token_source)

    return PollingCoordinator(
        AsyncSessionLocal,
        ingestion_factory=ingestion_factory,
        cadence=cadence_from_settings(),
        tracking_window=tracking_window_from_settings(),
    )


async def run_forever(
    coordinator: PollingCoordinator,
    *,
    tick: timedelta | None = None,
    stop: asyncio.Event | None = None,
) -> None:
    stop = stop or asyncio.Event()
    if tick is None:
        tick = timedelta(seconds=get_settings().intelligence_poll_tick_seconds)
    seconds = tick.total_seconds()

    while not stop.is_set():
        try:
            report = await coordinator.run_due()
            if report.claimed:
                logger.info(
                    "polled=%s written=%s unchanged=%s retrying=%s stopped=%s dead=%s",
                    report.claimed,
                    report.snapshots_written,
                    report.unchanged,
                    report.retrying,
                    report.stopped,
                    report.dead_lettered,
                )
        except Exception:  # noqa: BLE001
            # A tick failing (database down, say) must not kill the loop —
            # individual polls already handle their own failures, so
            # reaching here means something broader is wrong and the right
            # response is to log it and try again next tick.
            logger.exception("polling tick failed")

        try:
            await asyncio.wait_for(stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            continue


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(run_forever(build_coordinator()))


if __name__ == "__main__":
    main()
