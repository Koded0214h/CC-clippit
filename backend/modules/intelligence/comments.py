"""Fetch and store comment text — sampled, not exhaustive.

Decision D9: we do not crawl every comment on every poll. Platforms paginate
and rate-limit, and a 40,000-comment post would drown both the worker and
the fraud rules. Each successful observation pulls a bounded sample (a few
pages, a hard cap) and upserts by the platform's comment id.

TikTok's Display API has no comment text at all (`supports_comments` is
false there). This module is a no-op on that platform, which is the
correct behaviour — inventing an empty thread would look like "nobody
commented", and that's a different fact.

Failures here must not fail the poll. Metrics are the money path; comments
are evidence. Losing a sample is cheaper than losing an observation.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from integrations.social.base import AdapterError, PlatformComment, SocialPlatformAdapter

from . import repository
from .models import ContentComment, SocialContent
from .timeutils import utcnow

logger = logging.getLogger(__name__)

#: D9: a sample, not a census. Three pages is enough to see coordination
#: without spending the rate budget on a single viral post.
DEFAULT_MAX_PAGES = 3
DEFAULT_MAX_COMMENTS = 200

#: Strip URLs and collapse noise so "Nice!! http://x.com" and "nice" hash
#: together. Applied at evaluation time, never stored — the raw text is
#: what a reviewer reads.
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_NOISE_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """The comparison form. Not a semantic embedding — just enough that
    copy-pasted bot comments collapse into one bucket."""
    cleaned = _URL_RE.sub(" ", text.lower())
    cleaned = _NOISE_RE.sub(" ", cleaned)
    return _SPACE_RE.sub(" ", cleaned).strip()


async def sync(
    db: AsyncSession,
    content: SocialContent,
    adapter: SocialPlatformAdapter,
    *,
    access_token: str | None,
    clock=utcnow,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_comments: int = DEFAULT_MAX_COMMENTS,
) -> int:
    """Pull a sample and upsert it. Returns how many rows were written or
    refreshed. Never raises — see the module docstring."""
    if not adapter.supports_comments:
        return 0

    now = clock()
    fetched: list[PlatformComment] = []
    cursor: str | None = None

    try:
        for _ in range(max_pages):
            page = await adapter.get_comments(
                content.platform_content_id, access_token=access_token, cursor=cursor
            )
            fetched.extend(page.comments)
            if len(fetched) >= max_comments or not page.has_more:
                break
            cursor = page.next_cursor
            if not cursor:
                break
    except AdapterError as error:
        logger.warning(
            "comment sample failed for content %s (%s): %s",
            content.id,
            content.platform.value,
            error,
        )
        return 0

    written = 0
    for item in fetched[:max_comments]:
        await repository.upsert_comment(db, _to_row(content.id, item, now))
        written += 1
    return written


def _to_row(content_id: uuid.UUID, item: PlatformComment, now: datetime) -> ContentComment:
    return ContentComment(
        content_id=content_id,
        platform_comment_id=item.platform_comment_id,
        author_platform_user_id=item.author_platform_user_id,
        author_username=item.author_username,
        text=item.text,
        likes=item.likes,
        posted_at=item.created_at,
        first_seen_at=now,
        last_seen_at=now,
        raw=item.raw,
    )
