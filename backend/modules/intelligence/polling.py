"""The thing that turns one reading into a time series, unattended.

`run_due()` is the entire job: claim whatever is due, poll each one in its
own transaction, write down what happened and when to come back. A
scheduler — whichever one we land on in D4 — only has to call it on a
timer. Nothing in this file knows what Inngest or Celery is, and that's
the point: the runtime becomes a swappable detail rather than something
the polling logic is written around.

Three properties worth stating, because they're what make it safe to run
more than one of these at once:

1. **Each submission is its own transaction.** One creator's dead token
   can't roll back another creator's snapshot, and a batch of a hundred
   never fails as a unit.
2. **Work is leased, not just read.** Claiming pushes `next_poll_at`
   forward before any network call, so a second worker skips those rows
   and a crashed worker's rows come back on their own.
3. **A poll never raises.** Every failure becomes a recorded decision —
   retry, stop, or dead-letter — because an exception escaping here would
   take out the tick and every submission still queued behind it.

Policy lives next door in `scheduling.py`; this file is the machinery
that applies it.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from . import repository
from .contracts import SubmissionRef
from .features import FeatureService
from .ingestion import IngestionService
from .models import ContentTracking, SocialContent
from .scheduling import (
    DEFAULT_CADENCE,
    TRACKING_WINDOW,
    CadenceTier,
    FailureAction,
    TrackingStatus,
    decide,
    interval_for_age,
)
from .timeutils import as_utc, utcnow
from .trust_service import TrustService

logger = logging.getLogger(__name__)

#: How long a claimed row stays off the queue while it's being polled.
#: Only needs to comfortably exceed one poll (adapter timeouts are
#: seconds); longer just delays recovery from a crashed worker.
DEFAULT_LEASE = timedelta(minutes=5)

#: Rows per tick, and how many of those are in flight at once. Polling is
#: almost entirely waiting on someone else's API, so a little concurrency
#: goes a long way — but every platform has a rate ceiling, so this is a
#: deliberately small number rather than "as many as possible".
DEFAULT_BATCH_SIZE = 100
DEFAULT_CONCURRENCY = 5


@dataclass(frozen=True)
class PollResult:
    content_id: uuid.UUID
    status: TrackingStatus
    #: False either because the reading was an unchanged duplicate (D15)
    #: or because the poll failed.
    created_snapshot: bool
    snapshot_id: uuid.UUID | None
    next_poll_at: datetime | None
    #: "ok", "unchanged", "tracking_window_elapsed", or a failure code
    #: from `scheduling.decide()`.
    code: str
    message: str | None = None


@dataclass
class BatchReport:
    """One tick, summarized — enough for a log line or a metric without
    re-reading the database."""

    claimed: int = 0
    snapshots_written: int = 0
    unchanged: int = 0
    retrying: int = 0
    stopped: int = 0
    dead_lettered: int = 0
    results: list[PollResult] = field(default_factory=list)


class PollingCoordinator:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        ingestion_factory: Callable[[AsyncSession], IngestionService],
        clock: Callable[[], datetime] = utcnow,
        cadence: tuple[CadenceTier, ...] = DEFAULT_CADENCE,
        tracking_window: timedelta = TRACKING_WINDOW,
        lease: timedelta = DEFAULT_LEASE,
        batch_size: int = DEFAULT_BATCH_SIZE,
        concurrency: int = DEFAULT_CONCURRENCY,
    ) -> None:
        self._sessions = session_factory
        self._ingestion_factory = ingestion_factory
        self._clock = clock
        self._cadence = cadence
        self._tracking_window = tracking_window
        self._lease = lease
        self._batch_size = batch_size
        self._concurrency = concurrency

    # --- entry points ------------------------------------------------
    async def start(self, submission: SubmissionRef) -> PollResult:
        """Ingest a submission for the first time and put it on the queue.

        This is what core calls when a creator submits a link. It fails
        loudly rather than recording a decision — there's a human waiting
        on the response, and "your link isn't readable" is an answer they
        need immediately, not a dead-lettered row.
        """
        now = self._clock()
        async with self._sessions() as session:
            async with session.begin():
                outcome = await self._ingestion_factory(session).ingest(submission)
                content = await session.get(SocialContent, outcome.content_id)

                tracking = await repository.tracking_for_content(session, content.id)
                if tracking is None:
                    tracking = await repository.add_tracking(
                        session, ContentTracking(content_id=content.id, next_poll_at=now)
                    )
                tracking.status = TrackingStatus.active
                tracking.consecutive_failures = 0
                tracking.last_error_code = None
                tracking.last_error_message = None
                tracking.last_polled_at = now
                tracking.last_success_at = now
                await self._derive(session, content.id, outcome)
                result = self._schedule_next(tracking, content, now, outcome)
        return result

    async def run_due(self, limit: int | None = None) -> BatchReport:
        """One tick. Safe to call from anything that can call a coroutine
        on a timer, and safe to have several running at once."""
        now = self._clock()
        async with self._sessions() as session:
            async with session.begin():
                claimed = await repository.claim_due(
                    session, now=now, limit=limit or self._batch_size, lease=self._lease
                )

        report = BatchReport(claimed=len(claimed))
        if not claimed:
            return report

        semaphore = asyncio.Semaphore(self._concurrency)

        async def _guarded(content_id: uuid.UUID) -> PollResult:
            async with semaphore:
                return await self.poll(content_id)

        for result in await asyncio.gather(*(_guarded(cid) for cid in claimed)):
            _tally(report, result)
        return report

    async def poll(self, content_id: uuid.UUID) -> PollResult:
        """Read one submission's counters and decide when to come back."""
        now = self._clock()
        async with self._sessions() as session:
            async with session.begin():
                tracking = await repository.tracking_for_content(session, content_id)
                content = await session.get(SocialContent, content_id)
                if tracking is None or content is None:
                    # Claimed a row that vanished underneath us (content
                    # deleted mid-tick). Nothing to do and nothing to fix.
                    return PollResult(
                        content_id, TrackingStatus.stopped, False, None, None, "not_tracked"
                    )

                tracking.last_polled_at = now
                try:
                    outcome = await self._ingestion_factory(session).ingest(_submission_of(content))
                except Exception as error:  # noqa: BLE001 — see property 3 above
                    return self._handle_failure(tracking, error, now)

                tracking.consecutive_failures = 0
                tracking.last_error_code = None
                tracking.last_error_message = None
                tracking.last_success_at = now
                await self._derive(session, content_id, outcome)
                return self._schedule_next(tracking, content, now, outcome)

    async def stop(self, content_id: uuid.UUID, *, code: str, message: str | None = None) -> None:
        """Take a submission off the queue — campaign ended, submission
        withdrawn, admin intervention."""
        async with self._sessions() as session, session.begin():
            tracking = await repository.tracking_for_content(session, content_id)
            if tracking is None:
                return
            tracking.status = TrackingStatus.stopped
            tracking.last_error_code = code
            tracking.last_error_message = message

    async def resume(self, content_id: uuid.UUID) -> None:
        """Put a stopped or dead-lettered submission back on the queue,
        due immediately. This is what a creator reconnecting their account
        should trigger."""
        now = self._clock()
        async with self._sessions() as session, session.begin():
            tracking = await repository.tracking_for_content(session, content_id)
            if tracking is None:
                return
            tracking.status = TrackingStatus.active
            tracking.consecutive_failures = 0
            tracking.last_error_code = None
            tracking.last_error_message = None
            tracking.next_poll_at = now

    # --- internals ---------------------------------------------------
    async def _derive(self, session: AsyncSession, content_id: uuid.UUID, outcome) -> None:
        """Compute this observation's features in the same transaction that
        recorded it, so a snapshot is never visible without them.

        Skipped when the reading was a suppressed duplicate (D15): there's
        no new snapshot, and the existing one's features are already
        correct.
        """
        if not outcome.created_snapshot or outcome.snapshot_id is None:
            return
        await FeatureService(session, clock=self._clock).record_for_snapshot(
            content_id, outcome.snapshot_id
        )
        # Trust runs straight after features, in the same transaction, so
        # no observation is ever readable without a verdict attached.
        await TrustService(session, clock=self._clock).evaluate_latest(content_id)

    def _schedule_next(
        self,
        tracking: ContentTracking,
        content: SocialContent,
        now: datetime,
        outcome,
    ) -> PollResult:
        interval = interval_for_age(self._age_of(content, now), self._cadence)
        if interval is None:
            tracking.status = TrackingStatus.stopped
            tracking.last_error_code = "tracking_window_elapsed"
            tracking.last_error_message = (
                f"Older than the {self._tracking_window.days}-day tracking window."
            )
            return PollResult(
                content.id,
                TrackingStatus.stopped,
                outcome.created_snapshot,
                outcome.snapshot_id,
                None,
                "tracking_window_elapsed",
            )

        tracking.status = TrackingStatus.active
        tracking.next_poll_at = now + interval
        return PollResult(
            content.id,
            TrackingStatus.active,
            outcome.created_snapshot,
            outcome.snapshot_id,
            tracking.next_poll_at,
            "ok" if outcome.created_snapshot else "unchanged",
            outcome.skipped_reason,
        )

    def _handle_failure(
        self, tracking: ContentTracking, error: Exception, now: datetime
    ) -> PollResult:
        failures = tracking.consecutive_failures + 1
        decision = decide(error, consecutive_failures=failures)

        tracking.consecutive_failures = failures
        tracking.last_error_code = decision.code
        tracking.last_error_message = decision.message[:512]

        if decision.action is FailureAction.retry:
            tracking.status = TrackingStatus.active
            tracking.next_poll_at = now + (decision.delay or timedelta(minutes=1))
            logger.warning(
                "poll failed, retrying content_id=%s code=%s attempt=%s next=%s",
                tracking.content_id,
                decision.code,
                failures,
                tracking.next_poll_at,
            )
        else:
            tracking.status = (
                TrackingStatus.dead_lettered
                if decision.action is FailureAction.dead_letter
                else TrackingStatus.stopped
            )
            logger.warning(
                "poll stopped content_id=%s status=%s code=%s: %s",
                tracking.content_id,
                tracking.status.value,
                decision.code,
                decision.message,
            )

        return PollResult(
            content_id=tracking.content_id,
            status=tracking.status,
            created_snapshot=False,
            snapshot_id=None,
            next_poll_at=(
                tracking.next_poll_at if tracking.status is TrackingStatus.active else None
            ),
            code=decision.code,
            message=decision.message,
        )

    def _age_of(self, content: SocialContent, now: datetime) -> timedelta:
        """Age from the platform's publish time where we have it, falling
        back to when we first saw the post. `created_at` is server-side, so
        on the very first schedule (before any refresh) it's still None and
        the post is correctly treated as brand new."""
        basis = content.published_at or content.created_at
        return now - as_utc(basis) if basis else timedelta(0)


def _submission_of(content: SocialContent) -> SubmissionRef:
    """Rebuild the ingestion input from what we stored on first sight, so
    a poll needs nothing from Koded's tables at all."""
    return SubmissionRef(
        submission_id=content.submission_id,
        campaign_id=content.campaign_id,
        creator_id=content.creator_id,
        platform=content.platform,
        url=content.url,
    )


def _tally(report: BatchReport, result: PollResult) -> None:
    report.results.append(result)
    if result.created_snapshot:
        report.snapshots_written += 1
    elif result.code == "unchanged":
        report.unchanged += 1

    if result.status is TrackingStatus.dead_lettered:
        report.dead_lettered += 1
    elif result.status is TrackingStatus.stopped:
        report.stopped += 1
    elif result.code not in ("ok", "unchanged"):
        report.retrying += 1
