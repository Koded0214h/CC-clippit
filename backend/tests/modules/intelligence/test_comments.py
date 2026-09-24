"""Comment sampling: bounded, upserted, never fatal to a poll.

TikTok's adapter has `supports_comments=False`, so the money path stays
quiet there. These tests use a fake adapter that *does* return text, which
is what X / Instagram will look like once those adapters land.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from core.platforms import Platform
from integrations.social.base import (
    CommentPage,
    ContentKind,
    PlatformComment,
    PlatformContent,
    PlatformMetrics,
    PostType,
    UpstreamError,
)
from modules.intelligence.comments import normalize_text
from modules.intelligence.contracts import SubmissionRef
from modules.intelligence.ingestion import IngestionService
from modules.intelligence.models import ContentComment, SocialContent
from modules.intelligence.tokens import StaticTokenSource
from modules.intelligence.trust_service import TrustService

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
CAMPAIGN_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
T0 = datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc)
VIDEO_ID = "7401234567890123456"


class CommentingAdapter:
    platform = Platform.x
    source = "fake.comments"
    requires_creator_token = False
    supports_comments = True

    def __init__(self, page: CommentPage, *, fail: bool = False, observed_at: datetime = T0) -> None:
        self.page = page
        self.fail = fail
        self.observed_at = observed_at
        self.comment_calls = 0

    async def resolve_url(self, url: str) -> str | None:
        return VIDEO_ID

    async def get_content(self, content_id: str, *, access_token=None) -> PlatformContent:
        return PlatformContent(
            platform=Platform.x,
            platform_content_id=content_id,
            url=f"https://x.com/creator/status/{content_id}",
            kind=ContentKind.text,
            post_type=PostType.original,
            published_at=T0 - timedelta(days=1),
        )

    async def get_metrics(self, content_id: str, *, access_token=None) -> PlatformMetrics:
        return PlatformMetrics(
            platform=Platform.x,
            platform_content_id=content_id,
            observed_at=self.observed_at,
            views=5000,
            likes=200,
            comments=12,
        )

    async def get_comments(self, content_id: str, *, access_token=None, cursor=None) -> CommentPage:
        self.comment_calls += 1
        if self.fail:
            raise UpstreamError("comments endpoint 503")
        return self.page


def _page(*texts: str) -> CommentPage:
    return CommentPage(
        comments=[
            PlatformComment(
                platform=Platform.x,
                platform_comment_id=f"c{i}",
                platform_content_id=VIDEO_ID,
                text=text,
                author_platform_user_id=f"u{i}",
                created_at=T0 - timedelta(minutes=i),
            )
            for i, text in enumerate(texts)
        ]
    )


def _service(db, adapter) -> IngestionService:
    return IngestionService(
        db,
        token_source=StaticTokenSource({(CREATOR_ID, Platform.x): "x-token"}),
        adapter_lookup=lambda _platform: adapter,
    )


def _submission(submission_id: uuid.UUID | None = None) -> SubmissionRef:
    return SubmissionRef(
        submission_id=submission_id or uuid.uuid4(),
        campaign_id=CAMPAIGN_ID,
        creator_id=CREATOR_ID,
        platform=Platform.x,
        url=f"https://x.com/creator/status/{VIDEO_ID}",
    )


def test_normalize_collapses_punctuation_and_urls():
    assert normalize_text("Nice!! http://spam.example") == "nice"
    assert normalize_text("NICE") == normalize_text("nice...")


async def test_a_comment_sample_is_stored(db):
    adapter = CommentingAdapter(_page("one", "two", "three"))
    await _service(db, adapter).ingest(_submission())

    stored = list(await db.scalars(sa.select(ContentComment)))
    assert {row.text for row in stored} == {"one", "two", "three"}
    assert adapter.comment_calls == 1


async def test_re_fetching_the_same_comments_does_not_duplicate_them(db):
    ref = _submission()
    await _service(db, CommentingAdapter(_page("one", "two"))).ingest(ref)
    await _service(
        db, CommentingAdapter(_page("one", "two"), observed_at=T0 + timedelta(hours=2))
    ).ingest(ref)

    count = await db.scalar(sa.select(sa.func.count()).select_from(ContentComment))
    assert count == 2


async def test_a_failed_comment_fetch_does_not_lose_the_snapshot(db):
    adapter = CommentingAdapter(_page(), fail=True)
    outcome = await _service(db, adapter).ingest(_submission())

    assert outcome.created_snapshot is True
    assert await db.scalar(sa.select(sa.func.count()).select_from(ContentComment)) == 0
    assert await db.scalar(sa.select(sa.func.count()).select_from(SocialContent)) == 1


async def test_tiktok_never_asks_for_comment_text(db):
    """Capability flag, not a try/except. TikTok has no text API."""
    from tests.modules.intelligence.test_ingestion import FakeAdapter
    from tests.modules.intelligence.test_ingestion import _service as tiktok_service
    from tests.modules.intelligence.test_ingestion import _submission as tiktok_sub

    adapter = FakeAdapter()
    await tiktok_service(db, adapter).ingest(tiktok_sub())
    assert adapter.supports_comments is False
    assert await db.scalar(sa.select(sa.func.count()).select_from(ContentComment)) == 0


async def test_sampled_comments_reach_the_trust_verdict(db):
    """Stage 6 exit: comment evidence is in the trust result, not a side
    table nobody reads. Sentiment is not a signal code."""
    texts = ["Great video!!!"] * 12
    adapter = CommentingAdapter(_page(*texts))
    ref = _submission()
    await _service(db, adapter).ingest(ref)

    content = await db.scalar(
        sa.select(SocialContent).where(SocialContent.submission_id == ref.submission_id)
    )
    evaluation = await TrustService(db).evaluate_latest(content.id)

    codes = {s["code"] for s in evaluation.signals}
    assert "near_duplicate_comments" in codes
    assert all("sentiment" not in s["code"] for s in evaluation.signals)
