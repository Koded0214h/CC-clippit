"""Stage 3's exit condition and the failure paths around it.

The headline claim — a submission grows a time series over hours with
nobody watching — is `test_a_submission_grows_a_time_series_unattended`.
Everything else defends the edges: that work is leased rather than
duplicated, that a dead token stops polling instead of retrying forever,
that a transient outage backs off and eventually asks for a human, and
that one broken submission never takes the batch down with it.

Time is injected rather than slept through, so a fortnight of polling
runs in milliseconds.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa

from core.platforms import Platform
from integrations.social.base import (
    CommentPage,
    ContentKind,
    ContentUnavailable,
    PlatformContent,
    PlatformMetrics,
    PostType,
    RateLimited,
    UpstreamError,
)
from modules.intelligence import repository
from modules.intelligence.contracts import SubmissionRef
from modules.intelligence.ingestion import IngestionService
from modules.intelligence.models import ContentTracking, MetricSnapshot
from modules.intelligence.polling import DEFAULT_LEASE, PollingCoordinator
from modules.intelligence.scheduling import MAX_CONSECUTIVE_FAILURES, TrackingStatus
from modules.intelligence.tokens import StaticTokenSource

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
CAMPAIGN_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
T0 = datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, start: datetime = T0) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class ClockedAdapter:
    """A platform whose view count rises with the clock, and which can be
    told to fail — for everything, or for one specific post."""

    platform = Platform.tiktok
    source = "fake.api"
    requires_creator_token = True
    supports_comments = False

    def __init__(
        self,
        clock: FakeClock,
        *,
        published_at: datetime | None = None,
        views_per_hour: int = 600,
    ) -> None:
        self._clock = clock
        self._published_at = published_at if published_at is not None else T0 - timedelta(hours=1)
        self._views_per_hour = views_per_hour
        self.error: Exception | None = None
        self.fail_for: dict[str, Exception] = {}
        self.metrics_calls = 0

    async def resolve_url(self, url: str) -> str | None:
        return url.rsplit("/", 1)[-1]

    async def get_content(self, content_id: str, *, access_token: str | None = None) -> PlatformContent:
        return PlatformContent(
            platform=Platform.tiktok,
            platform_content_id=content_id,
            url=f"https://www.tiktok.com/@creator/video/{content_id}",
            author_username="creator",
            kind=ContentKind.video,
            post_type=PostType.original,
            published_at=self._published_at,
        )

    async def get_metrics(self, content_id: str, *, access_token: str | None = None) -> PlatformMetrics:
        self.metrics_calls += 1
        failure = self.fail_for.get(content_id) or self.error
        if failure:
            raise failure

        elapsed_hours = (self._clock() - T0).total_seconds() / 3600
        return PlatformMetrics(
            platform=Platform.tiktok,
            platform_content_id=content_id,
            observed_at=self._clock(),
            views=1000 + int(elapsed_hours * self._views_per_hour),
            likes=50,
        )

    async def get_comments(self, content_id: str, *, access_token=None, cursor=None) -> CommentPage:
        raise AssertionError("not used")


def _submission(video_id: str = "7401234567890123456") -> SubmissionRef:
    return SubmissionRef(
        submission_id=uuid.uuid4(),
        campaign_id=CAMPAIGN_ID,
        creator_id=CREATOR_ID,
        platform=Platform.tiktok,
        url=f"https://www.tiktok.com/@creator/video/{video_id}",
    )


def _coordinator(session_factory, adapter, clock, *, token="tok", dedupe=None, **kwargs):
    tokens = StaticTokenSource({(CREATOR_ID, Platform.tiktok): token} if token else {})

    def ingestion_factory(session):
        extra = {"dedupe_window": dedupe} if dedupe else {}
        return IngestionService(
            session, token_source=tokens, adapter_lookup=lambda _: adapter, **extra
        )

    # concurrency=1: the in-memory SQLite database is a single shared
    # connection, so parallel sessions would contend on it. The production
    # default is higher; what's under test here is the policy, not asyncio.
    return PollingCoordinator(
        session_factory, ingestion_factory=ingestion_factory, clock=clock, concurrency=1, **kwargs
    )


async def _tracking(session_factory, content_id) -> ContentTracking:
    async with session_factory() as session:
        return await session.get(ContentTracking, content_id)


async def _snapshots(session_factory, content_id) -> list[MetricSnapshot]:
    async with session_factory() as session:
        return await repository.snapshots_for_content(session, content_id)


async def test_start_takes_a_first_reading_and_queues_the_next(session_factory):
    clock = FakeClock()
    coordinator = _coordinator(session_factory, ClockedAdapter(clock), clock)

    result = await coordinator.start(_submission())

    assert result.status is TrackingStatus.active
    assert result.created_snapshot
    assert result.next_poll_at == T0 + timedelta(minutes=30)
    assert len(await _snapshots(session_factory, result.content_id)) == 1


async def test_nothing_is_polled_before_it_is_due(session_factory):
    clock = FakeClock()
    coordinator = _coordinator(session_factory, ClockedAdapter(clock), clock)
    await coordinator.start(_submission())

    clock.advance(timedelta(minutes=20))
    assert (await coordinator.run_due()).claimed == 0

    clock.advance(timedelta(minutes=15))
    assert (await coordinator.run_due()).claimed == 1


async def test_a_submission_grows_a_time_series_unattended(session_factory):
    """Stage 3's exit condition: start it once, tick a clock, walk away."""
    clock = FakeClock()
    coordinator = _coordinator(session_factory, ClockedAdapter(clock), clock)
    started = await coordinator.start(_submission())

    for _ in range(6):
        clock.advance(timedelta(minutes=31))
        await coordinator.run_due()

    series = await _snapshots(session_factory, started.content_id)
    assert len(series) == 7, "one reading from start(), six from the ticks"

    captured = [s.captured_at for s in series]
    views = [s.views for s in series]
    assert captured == sorted(captured), "the series must be chronological"
    assert views == sorted(views) and views[0] < views[-1], "and must actually show growth"


async def test_cadence_widens_once_a_post_is_a_day_old(session_factory):
    clock = FakeClock()
    adapter = ClockedAdapter(clock, published_at=T0 - timedelta(hours=25))
    coordinator = _coordinator(session_factory, adapter, clock)

    result = await coordinator.start(_submission())

    assert result.next_poll_at == T0 + timedelta(hours=2)


async def test_a_post_past_the_tracking_window_is_not_queued_again(session_factory):
    clock = FakeClock()
    adapter = ClockedAdapter(clock, published_at=T0 - timedelta(days=31))
    coordinator = _coordinator(session_factory, adapter, clock)

    result = await coordinator.start(_submission())

    assert result.status is TrackingStatus.stopped
    assert result.code == "tracking_window_elapsed"
    assert result.created_snapshot, "the final reading is still recorded"

    clock.advance(timedelta(days=1))
    assert (await coordinator.run_due()).claimed == 0


async def test_rate_limiting_waits_exactly_as_long_as_the_provider_asked(session_factory):
    clock = FakeClock()
    adapter = ClockedAdapter(clock)
    coordinator = _coordinator(session_factory, adapter, clock)
    started = await coordinator.start(_submission())

    adapter.error = RateLimited("slow down", retry_after=90)
    clock.advance(timedelta(minutes=31))
    report = await coordinator.run_due()

    assert report.retrying == 1
    assert report.snapshots_written == 0
    tracking = await _tracking(session_factory, started.content_id)
    assert tracking.status is TrackingStatus.active
    assert tracking.next_poll_at.replace(tzinfo=timezone.utc) == clock.now + timedelta(seconds=90)
    assert tracking.consecutive_failures == 1


async def test_a_sustained_outage_backs_off_then_asks_for_a_human(session_factory):
    clock = FakeClock()
    adapter = ClockedAdapter(clock)
    coordinator = _coordinator(session_factory, adapter, clock)
    started = await coordinator.start(_submission())
    adapter.error = UpstreamError("502 from the platform")

    for _ in range(MAX_CONSECUTIVE_FAILURES):
        clock.advance(timedelta(hours=2))  # always past the current backoff
        await coordinator.run_due()

    tracking = await _tracking(session_factory, started.content_id)
    assert tracking.status is TrackingStatus.dead_lettered
    assert tracking.consecutive_failures == MAX_CONSECUTIVE_FAILURES
    assert "gave up" in tracking.last_error_message

    clock.advance(timedelta(days=1))
    assert (await coordinator.run_due()).claimed == 0, "dead-lettered work stays off the queue"


async def test_a_recovered_failure_clears_the_counter(session_factory):
    clock = FakeClock()
    adapter = ClockedAdapter(clock)
    coordinator = _coordinator(session_factory, adapter, clock)
    started = await coordinator.start(_submission())

    adapter.error = UpstreamError("blip")
    clock.advance(timedelta(minutes=31))
    await coordinator.run_due()

    adapter.error = None
    clock.advance(timedelta(hours=1))
    await coordinator.run_due()

    tracking = await _tracking(session_factory, started.content_id)
    assert tracking.consecutive_failures == 0
    assert tracking.last_error_code is None
    assert len(await _snapshots(session_factory, started.content_id)) == 2


async def test_content_that_went_private_stops_and_records_why(session_factory):
    clock = FakeClock()
    adapter = ClockedAdapter(clock)
    coordinator = _coordinator(session_factory, adapter, clock)
    started = await coordinator.start(_submission())

    adapter.error = ContentUnavailable("creator made the post private")
    clock.advance(timedelta(minutes=31))
    await coordinator.run_due()

    tracking = await _tracking(session_factory, started.content_id)
    assert tracking.status is TrackingStatus.stopped
    assert tracking.last_error_code == "content_unavailable"


async def test_a_disconnected_creator_stops_polling_rather_than_retrying(session_factory):
    """No token means every retry is guaranteed to fail identically, so
    the only useful move is to stop and ask them to reconnect."""
    clock = FakeClock()
    coordinator = _coordinator(session_factory, ClockedAdapter(clock), clock)
    started = await coordinator.start(_submission())

    # The creator disconnects the account between polls.
    disconnected = _coordinator(session_factory, ClockedAdapter(clock), clock, token=None)
    clock.advance(timedelta(minutes=31))
    await disconnected.run_due()

    tracking = await _tracking(session_factory, started.content_id)
    assert tracking.status is TrackingStatus.stopped
    assert tracking.last_error_code == "creator_reconnect_required"


async def test_resume_puts_a_stopped_submission_back_on_the_queue(session_factory):
    clock = FakeClock()
    adapter = ClockedAdapter(clock)
    coordinator = _coordinator(session_factory, adapter, clock)
    started = await coordinator.start(_submission())

    adapter.error = ContentUnavailable("private")
    clock.advance(timedelta(minutes=31))
    await coordinator.run_due()

    adapter.error = None
    await coordinator.resume(started.content_id)
    report = await coordinator.run_due()

    assert report.claimed == 1
    assert report.snapshots_written == 1
    tracking = await _tracking(session_factory, started.content_id)
    assert tracking.status is TrackingStatus.active
    assert tracking.consecutive_failures == 0


async def test_one_broken_submission_does_not_affect_the_rest_of_the_batch(session_factory):
    clock = FakeClock()
    adapter = ClockedAdapter(clock)
    coordinator = _coordinator(session_factory, adapter, clock)
    broken = await coordinator.start(_submission("1111111111111111111"))
    healthy = await coordinator.start(_submission("2222222222222222222"))

    adapter.fail_for["1111111111111111111"] = UpstreamError("502")
    clock.advance(timedelta(minutes=31))
    report = await coordinator.run_due()

    assert report.claimed == 2
    assert report.snapshots_written == 1
    assert len(await _snapshots(session_factory, healthy.content_id)) == 2
    assert len(await _snapshots(session_factory, broken.content_id)) == 1


async def test_claimed_work_is_leased_so_a_second_worker_skips_it(session_factory):
    """Two workers on one tick must not poll the same submission twice —
    and if the first one dies, the lease has to expire."""
    clock = FakeClock()
    coordinator = _coordinator(session_factory, ClockedAdapter(clock), clock)
    started = await coordinator.start(_submission())
    clock.advance(timedelta(minutes=31))

    async with session_factory() as session, session.begin():
        first = await repository.claim_due(
            session, now=clock.now, limit=10, lease=DEFAULT_LEASE
        )
    async with session_factory() as session, session.begin():
        second = await repository.claim_due(
            session, now=clock.now, limit=10, lease=DEFAULT_LEASE
        )

    assert first == [started.content_id]
    assert second == [], "the lease keeps a concurrent worker off the same row"

    clock.advance(DEFAULT_LEASE + timedelta(seconds=1))
    async with session_factory() as session, session.begin():
        after_expiry = await repository.claim_due(
            session, now=clock.now, limit=10, lease=DEFAULT_LEASE
        )
    assert after_expiry == [started.content_id], "a crashed worker's row must come back"


async def test_an_unchanged_reading_still_counts_as_a_successful_poll(session_factory):
    """Dedupe (D15) suppressing a write is not a failure — the submission
    stays on its normal cadence."""
    clock = FakeClock()
    adapter = ClockedAdapter(clock, views_per_hour=0)
    coordinator = _coordinator(session_factory, adapter, clock, dedupe=timedelta(hours=2))
    started = await coordinator.start(_submission())

    clock.advance(timedelta(minutes=31))
    report = await coordinator.run_due()

    assert (report.unchanged, report.snapshots_written) == (1, 0)
    assert len(await _snapshots(session_factory, started.content_id)) == 1
    tracking = await _tracking(session_factory, started.content_id)
    assert tracking.status is TrackingStatus.active
    assert tracking.consecutive_failures == 0


async def test_a_tick_only_takes_what_it_can_chew(session_factory):
    clock = FakeClock()
    coordinator = _coordinator(session_factory, ClockedAdapter(clock), clock)
    for i in range(3):
        await coordinator.start(_submission(f"{i}00000000000000000"))

    clock.advance(timedelta(minutes=31))
    assert (await coordinator.run_due(limit=2)).claimed == 2
    assert (await coordinator.run_due(limit=2)).claimed == 1


@pytest.mark.parametrize("status", [TrackingStatus.stopped, TrackingStatus.dead_lettered])
async def test_only_active_rows_are_ever_claimed(session_factory, status):
    clock = FakeClock()
    coordinator = _coordinator(session_factory, ClockedAdapter(clock), clock)
    started = await coordinator.start(_submission())

    async with session_factory() as session, session.begin():
        tracking = await session.get(ContentTracking, started.content_id)
        tracking.status = status

    clock.advance(timedelta(days=1))
    assert (await coordinator.run_due()).claimed == 0

    async with session_factory() as session:
        remaining = await session.scalar(
            sa.select(sa.func.count()).select_from(MetricSnapshot)
        )
    assert remaining == 1
