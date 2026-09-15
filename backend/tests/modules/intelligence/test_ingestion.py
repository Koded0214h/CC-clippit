"""Stage 2's guarantees, stated as tests.

The claims being defended, in order: identity is stored once and reused,
observations accumulate and are never rewritten, a retried job can't
pollute the series, absent metrics stay absent, provenance is always
recorded, and a failure writes nothing.

The adapter is a fake rather than a mocked-out `TikTokAdapter` — this
suite is about the ingestion *policy*, and the real adapter already has
its own tests against captured payloads.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa

from core.platforms import Platform
from integrations.social.base import (
    CapabilityNotSupported,
    CommentPage,
    ContentKind,
    PlatformContent,
    PlatformMetrics,
    PostType,
    SocialPlatformAdapter,
)
from modules.intelligence.contracts import SubmissionRef
from modules.intelligence.errors import MissingCreatorToken, UrlNotRecognized
from modules.intelligence.ingestion import IngestionService
from modules.intelligence.models import MetricSnapshot, SocialContent
from modules.intelligence.tokens import StaticTokenSource

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
CAMPAIGN_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
POST_URL = "https://www.tiktok.com/@creator/video/7401234567890123456"
T0 = datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc)


class FakeAdapter:
    """A platform that does exactly what the test tells it to, and counts
    how often it was asked."""

    platform = Platform.tiktok
    source = "fake.api"
    requires_creator_token = True
    supports_comments = False

    def __init__(self, *, content_id: str = "7401234567890123456", resolves: bool = True) -> None:
        self.content_id = content_id
        self.resolves = resolves
        self.metrics = _metrics(views=1000, observed_at=T0)
        self.resolve_calls = 0
        self.content_calls = 0
        self.metrics_calls = 0
        self.tokens_seen: list[str | None] = []

    async def resolve_url(self, url: str) -> str | None:
        self.resolve_calls += 1
        return self.content_id if self.resolves else None

    async def get_content(self, content_id: str, *, access_token: str | None = None) -> PlatformContent:
        self.content_calls += 1
        self.tokens_seen.append(access_token)
        return PlatformContent(
            platform=Platform.tiktok,
            platform_content_id=content_id,
            url=f"https://www.tiktok.com/@creator/video/{content_id}",
            author_username="creator",
            kind=ContentKind.video,
            post_type=PostType.original,
            published_at=T0 - timedelta(days=1),
            raw={"id": content_id, "title": "a video"},
        )

    async def get_metrics(self, content_id: str, *, access_token: str | None = None) -> PlatformMetrics:
        self.metrics_calls += 1
        self.tokens_seen.append(access_token)
        return self.metrics

    async def get_comments(self, content_id: str, *, access_token=None, cursor=None) -> CommentPage:
        raise CapabilityNotSupported("fake adapter has no comments")


def _metrics(*, views: int | None, observed_at: datetime, likes: int | None = 50) -> PlatformMetrics:
    return PlatformMetrics(
        platform=Platform.tiktok,
        platform_content_id="7401234567890123456",
        observed_at=observed_at,
        views=views,
        likes=likes,
        comments=5,
        shares=2,
        raw={"view_count": views},
    )


def _submission(submission_id: uuid.UUID | None = None, url: str = POST_URL) -> SubmissionRef:
    return SubmissionRef(
        submission_id=submission_id or uuid.uuid4(),
        campaign_id=CAMPAIGN_ID,
        creator_id=CREATOR_ID,
        platform=Platform.tiktok,
        url=url,
    )


def _service(db, adapter, *, token: str | None = "creator-token", **kwargs) -> IngestionService:
    tokens = StaticTokenSource({(CREATOR_ID, Platform.tiktok): token} if token else {})
    return IngestionService(db, token_source=tokens, adapter_lookup=lambda _: adapter, **kwargs)


async def _count(db, model) -> int:
    return await db.scalar(sa.select(sa.func.count()).select_from(model))


def test_fake_adapter_satisfies_the_protocol():
    # If this fails, the fake has drifted from the real contract and every
    # other test in this file is testing fiction.
    assert isinstance(FakeAdapter(), SocialPlatformAdapter)


async def test_first_ingest_stores_identity_and_one_observation(db):
    adapter = FakeAdapter()
    submission = _submission()

    outcome = await _service(db, adapter).ingest(submission)

    assert outcome.created_content and outcome.created_snapshot
    content = await db.get(SocialContent, outcome.content_id)
    assert content.submission_id == submission.submission_id
    assert content.campaign_id == CAMPAIGN_ID
    assert content.platform is Platform.tiktok
    assert content.platform_content_id == "7401234567890123456"
    assert content.author_username == "creator"
    assert content.kind is ContentKind.video
    assert content.post_type is PostType.original

    snapshot = await db.get(MetricSnapshot, outcome.snapshot_id)
    assert (snapshot.views, snapshot.likes, snapshot.comments, snapshot.shares) == (1000, 50, 5, 2)


async def test_second_ingest_appends_and_leaves_the_first_untouched(db):
    """The core append-only claim: history accumulates, nothing is rewritten."""
    adapter = FakeAdapter()
    service = _service(db, adapter)
    submission = _submission()

    first = await service.ingest(submission)
    adapter.metrics = _metrics(views=4200, observed_at=T0 + timedelta(hours=1))
    second = await service.ingest(submission)

    assert await _count(db, SocialContent) == 1, "re-ingesting must reuse the content row"
    assert second.created_content is False
    assert await _count(db, MetricSnapshot) == 2
    assert second.snapshot_id != first.snapshot_id

    original = await db.get(MetricSnapshot, first.snapshot_id)
    assert original.views == 1000, "the earlier observation must survive verbatim"


async def test_polling_does_not_re_resolve_identity(db):
    """Three API calls on the first ingest, one on every one after — the
    difference between polling thousands of submissions and being rate
    limited into the ground."""
    adapter = FakeAdapter()
    service = _service(db, adapter)
    submission = _submission()

    await service.ingest(submission)
    adapter.metrics = _metrics(views=2000, observed_at=T0 + timedelta(hours=1))
    await service.ingest(submission)

    assert (adapter.resolve_calls, adapter.content_calls, adapter.metrics_calls) == (1, 1, 2)


async def test_identical_reading_within_the_window_is_not_stored(db):
    """A retried job re-reads the same numbers seconds later. Recording
    that as a second data point would fake a zero-growth interval."""
    adapter = FakeAdapter()
    service = _service(db, adapter)
    submission = _submission()

    first = await service.ingest(submission)
    adapter.metrics = _metrics(views=1000, observed_at=T0 + timedelta(seconds=5))
    second = await service.ingest(submission)

    assert second.created_snapshot is False
    assert second.snapshot_id == first.snapshot_id
    assert second.skipped_reason
    assert await _count(db, MetricSnapshot) == 1


async def test_changed_counters_within_the_window_are_stored(db):
    """Movement is always real data, however soon it arrives."""
    adapter = FakeAdapter()
    service = _service(db, adapter)
    submission = _submission()

    await service.ingest(submission)
    adapter.metrics = _metrics(views=1001, observed_at=T0 + timedelta(seconds=5))
    outcome = await service.ingest(submission)

    assert outcome.created_snapshot
    assert await _count(db, MetricSnapshot) == 2


async def test_unchanged_counters_after_the_window_are_stored(db):
    """"This post gained nothing in an hour" is a finding, not a duplicate."""
    adapter = FakeAdapter()
    service = _service(db, adapter)
    submission = _submission()

    await service.ingest(submission)
    adapter.metrics = _metrics(views=1000, observed_at=T0 + timedelta(hours=1))
    outcome = await service.ingest(submission)

    assert outcome.created_snapshot
    assert await _count(db, MetricSnapshot) == 2


async def test_captured_at_is_the_observation_time_not_the_write_time(db):
    adapter = FakeAdapter()
    outcome = await _service(db, adapter).ingest(_submission())

    snapshot = await db.get(MetricSnapshot, outcome.snapshot_id)
    assert snapshot.captured_at.replace(tzinfo=timezone.utc) == T0


async def test_unreported_metrics_stay_null(db):
    """TikTok reports no `saves` or `reach`. Storing 0 would read as
    "nobody saved it" and quietly poison every ratio built on it."""
    adapter = FakeAdapter()
    outcome = await _service(db, adapter).ingest(_submission())

    snapshot = await db.get(MetricSnapshot, outcome.snapshot_id)
    assert snapshot.saves is None
    assert snapshot.reach is None
    assert snapshot.impressions is None


async def test_provenance_and_raw_payload_are_recorded(db):
    adapter = FakeAdapter()
    outcome = await _service(db, adapter).ingest(_submission())

    snapshot = await db.get(MetricSnapshot, outcome.snapshot_id)
    assert snapshot.source == "fake.api"
    assert snapshot.raw_metrics == {"view_count": 1000}

    content = await db.get(SocialContent, outcome.content_id)
    assert content.raw_content["title"] == "a video"


async def test_the_creator_token_reaches_the_adapter(db):
    adapter = FakeAdapter()
    await _service(db, adapter, token="creator-token").ingest(_submission())

    assert adapter.tokens_seen == ["creator-token", "creator-token"]


async def test_missing_token_fails_before_any_platform_call(db):
    adapter = FakeAdapter()

    with pytest.raises(MissingCreatorToken):
        await _service(db, adapter, token=None).ingest(_submission())

    assert adapter.resolve_calls == 0, "don't spend an API call we can't authenticate"
    assert await _count(db, SocialContent) == 0


async def test_unrecognised_url_raises_and_writes_nothing(db):
    adapter = FakeAdapter(resolves=False)

    with pytest.raises(UrlNotRecognized):
        await _service(db, adapter).ingest(_submission(url="https://www.tiktok.com/@creator"))

    assert await _count(db, SocialContent) == 0
    assert await _count(db, MetricSnapshot) == 0


async def test_two_submissions_of_the_same_post_both_persist(db):
    """Duplicate submissions are a trust signal to detect later, so the
    schema has to let both rows exist rather than reject the second."""
    adapter = FakeAdapter()
    service = _service(db, adapter)

    await service.ingest(_submission())
    await service.ingest(_submission())

    rows = (await db.scalars(sa.select(SocialContent))).all()
    assert len(rows) == 2
    assert len({row.platform_content_id for row in rows}) == 1
