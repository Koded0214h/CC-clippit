"""Ownership must fail closed for API-key platforms (YouTube / X)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from core.platforms import Platform
from integrations.social.base import ContentKind, ContentUnavailable, PlatformContent, PlatformMetrics, PostType
from modules.intelligence.contracts import SubmissionRef
from modules.intelligence.ingestion import IngestionService
from modules.intelligence.tokens import StaticTokenSource

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
CAMPAIGN_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
T0 = datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc)


class _YtAdapter:
    platform = Platform.youtube
    source = "fake.youtube"
    requires_creator_token = False
    supports_comments = False

    def __init__(self, author_id: str | None) -> None:
        self.author_id = author_id

    async def resolve_url(self, url: str) -> str | None:
        return "dQw4w9WgXcQ"

    async def get_content(self, content_id: str, *, access_token=None) -> PlatformContent:
        return PlatformContent(
            platform=Platform.youtube,
            platform_content_id=content_id,
            url=f"https://www.youtube.com/watch?v={content_id}",
            author_platform_user_id=self.author_id,
            kind=ContentKind.video,
            post_type=PostType.original,
            published_at=T0 - timedelta(days=1),
        )

    async def get_metrics(self, content_id: str, *, access_token=None) -> PlatformMetrics:
        return PlatformMetrics(
            platform=Platform.youtube,
            platform_content_id=content_id,
            observed_at=T0,
            views=100,
        )

    async def get_comments(self, *a, **k):
        raise NotImplementedError


async def test_ownership_mismatch_is_rejected(db):
    adapter = _YtAdapter("UCsomeoneelse")
    tokens = StaticTokenSource(
        {(CREATOR_ID, Platform.youtube): "tok"},
        platform_user_ids={(CREATOR_ID, Platform.youtube): "UCmine"},
    )
    service = IngestionService(db, token_source=tokens, adapter_lookup=lambda _: adapter)
    with pytest.raises(ContentUnavailable, match="not the connected account"):
        await service.ingest(
            SubmissionRef(
                submission_id=uuid.uuid4(),
                campaign_id=CAMPAIGN_ID,
                creator_id=CREATOR_ID,
                platform=Platform.youtube,
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            )
        )


async def test_missing_author_id_fails_closed(db):
    adapter = _YtAdapter(None)
    tokens = StaticTokenSource(
        {(CREATOR_ID, Platform.youtube): "tok"},
        platform_user_ids={(CREATOR_ID, Platform.youtube): "UCmine"},
    )
    service = IngestionService(db, token_source=tokens, adapter_lookup=lambda _: adapter)
    with pytest.raises(ContentUnavailable, match="Cannot verify"):
        await service.ingest(
            SubmissionRef(
                submission_id=uuid.uuid4(),
                campaign_id=CAMPAIGN_ID,
                creator_id=CREATOR_ID,
                platform=Platform.youtube,
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            )
        )
