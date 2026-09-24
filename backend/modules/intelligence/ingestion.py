"""Turn a submission into stored observations.

    ingest(submission) ->  resolve the URL once
                           read the post's identity once
                           read its counters every time
                           append a snapshot

The asymmetry in that sketch is the point. Identity is resolved on the
**first** ingest and reused forever after, so polling a submission for two
weeks costs one API call per poll instead of three. At TikTok's 600
requests/minute that difference decides how many creators we can watch.

What this service deliberately does *not* do:

- **Commit.** One ingest is one unit of work — a content row and its first
  snapshot land together or not at all — so the caller owns the
  transaction and can retry cleanly.
- **Retry.** Adapter errors propagate untouched for the Stage 3 poller to
  interpret (decision D13).
- **Judge.** No thresholds, no eligibility, no payout logic. It records
  what the platform said and stops.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from core.platforms import Platform
from integrations.social import get_adapter
from integrations.social.base import ContentUnavailable, PostType, SocialPlatformAdapter

from . import comments, normalizer, repository
from .contracts import SubmissionRef
from .errors import IneligibleContent, UrlNotRecognized
from .models import MetricSnapshot, SocialContent
from .timeutils import as_utc
from .tokens import CreatorCredential, TokenSource

#: How close to the previous observation a *numerically identical* reading
#: has to be before we treat it as a duplicate write rather than a real
#: second data point. Guards against a retried job (or an impatient
#: refresh) stamping the time series with rows that carry no information.
DEFAULT_DEDUPE_WINDOW = timedelta(seconds=60)


@dataclass(frozen=True)
class IngestOutcome:
    """What one ingest actually changed — enough for a job to log a useful
    line without re-querying, and for a test to assert on."""

    content_id: uuid.UUID
    snapshot_id: uuid.UUID | None
    created_content: bool
    created_snapshot: bool
    skipped_reason: str | None = None


class IngestionService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        token_source: TokenSource,
        adapter_lookup: Callable[[Platform], SocialPlatformAdapter] = get_adapter,
        dedupe_window: timedelta = DEFAULT_DEDUPE_WINDOW,
    ) -> None:
        self._db = db
        self._tokens = token_source
        self._adapter_lookup = adapter_lookup
        self._dedupe_window = dedupe_window

    async def ingest(self, submission: SubmissionRef) -> IngestOutcome:
        adapter = self._adapter_lookup(submission.platform)

        content = await repository.content_for_submission(self._db, submission.submission_id)
        created_content = content is None

        # Token platforms need the creator OAuth token for every poll.
        # API-key platforms (YouTube, X) only need the connected-account
        # identity on first resolve, to prove the post belongs to them.
        credential: CreatorCredential | None = None
        if adapter.requires_creator_token or content is None:
            credential = await self._tokens.credential_for(
                submission.creator_id, submission.platform
            )
        token = credential.access_token if credential and adapter.requires_creator_token else None

        if content is None:
            content = await self._resolve_and_store(
                submission, adapter, token, credential=credential
            )

        metrics = await adapter.get_metrics(content.platform_content_id, access_token=token)

        previous = await repository.latest_snapshot(self._db, content.id)
        if previous is not None and self._is_duplicate(previous, metrics):
            return IngestOutcome(
                content_id=content.id,
                snapshot_id=previous.id,
                created_content=created_content,
                created_snapshot=False,
                skipped_reason="identical counters within the dedupe window",
            )

        snapshot = await repository.add_snapshot(
            self._db, normalizer.build_snapshot(content.id, metrics, adapter.source)
        )
        # Comments are evidence, not the money path. A failed sample must
        # not roll back the observation we just wrote.
        await comments.sync(self._db, content, adapter, access_token=token)
        return IngestOutcome(
            content_id=content.id,
            snapshot_id=snapshot.id,
            created_content=created_content,
            created_snapshot=True,
        )

    async def _resolve_and_store(
        self,
        submission: SubmissionRef,
        adapter: SocialPlatformAdapter,
        token: str | None,
        *,
        credential: CreatorCredential | None = None,
    ) -> SocialContent:
        content_id = await adapter.resolve_url(submission.url)
        if not content_id:
            raise UrlNotRecognized(
                f"{submission.url!r} is not a recognisable {submission.platform.value} post URL."
            )

        platform_content = await adapter.get_content(content_id, access_token=token)
        if platform_content.post_type not in (PostType.original, PostType.quote):
            raise IneligibleContent(
                f"A {platform_content.post_type.value} cannot be submitted — "
                "only original posts and quotes count."
            )
        # API-key adapters can read any public URL. Ownership must be
        # proven — fail closed if either side of the comparison is missing.
        if not adapter.requires_creator_token:
            connected_id = credential.platform_user_id if credential else None
            author_id = platform_content.author_platform_user_id
            if not connected_id or not author_id:
                raise ContentUnavailable(
                    f"Cannot verify {submission.platform.value} ownership — "
                    "missing connected account id or post author id."
                )
            if connected_id != author_id:
                raise ContentUnavailable(
                    f"This {submission.platform.value} post belongs to "
                    f"{author_id}, not the connected account ({connected_id})."
                )
        return await repository.add_content(
            self._db, normalizer.build_content(submission, platform_content)
        )

    def _is_duplicate(self, previous: MetricSnapshot, metrics) -> bool:
        within_window = (
            as_utc(metrics.observed_at) - as_utc(previous.captured_at)
        ) < self._dedupe_window
        return within_window and normalizer.counters_match(previous, metrics)
