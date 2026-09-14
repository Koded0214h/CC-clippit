"""Assembling the answer to "how is this submission doing?".

Pure reads. Nothing here calls a platform — by the time earnings asks,
the numbers are already in our tables, put there by the poller. That
separation is deliberate and load-bearing: a billing run must never be
slow, rate limited, or wrong because TikTok happened to be down.

This module is also the last gate before data leaves the domain. It maps
rows to `contracts.py` models by hand rather than serializing the ORM
objects, which is what keeps `raw_metrics`, provider payloads and internal
error strings from leaking into someone else's service.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from . import features, normalizer, repository
from .contracts import (
    ContentIdentity,
    PerformanceFeatures,
    PerformanceResult,
    Provenance,
    TrackingState,
)
from .models import MetricSnapshot, SocialContent
from .timeutils import as_utc


async def performance_for_submission(
    db: AsyncSession,
    submission_id: uuid.UUID,
    *,
    since_snapshot_id: uuid.UUID | None = None,
) -> PerformanceResult | None:
    """The full picture for one submission, or None if we've never seen it.

    `since_snapshot_id` lets a caller ask "what has accrued since the
    snapshot I last settled against", which is the only form of the
    question that gives the same answer twice. See decision D18.
    """
    content = await repository.content_for_submission(db, submission_id)
    if content is None:
        return None

    latest = await repository.latest_snapshot(db, content.id)
    if latest is None:
        # A tracked post with no observations shouldn't exist — `start()`
        # writes one — but returning a result with invented numbers would
        # be worse than saying we have nothing.
        return None

    return PerformanceResult(
        submission_id=submission_id,
        content=_identity(content),
        metrics=normalizer.metrics_block(latest),
        features=await _features(db, content.id, latest, since_snapshot_id),
        provenance=Provenance(
            platform=content.platform,
            source=latest.source,
            snapshot_id=latest.id,
            observed_at=as_utc(latest.captured_at),
        ),
        tracking=await _tracking(db, content.id),
    )


def _identity(content: SocialContent) -> ContentIdentity:
    return ContentIdentity(
        platform=content.platform,
        platform_content_id=content.platform_content_id,
        url=content.url,
        author_username=content.author_username,
        kind=content.kind,
        post_type=content.post_type,
        published_at=as_utc(content.published_at) if content.published_at else None,
    )


async def _features(
    db: AsyncSession,
    content_id: uuid.UUID,
    latest: MetricSnapshot,
    since_snapshot_id: uuid.UUID | None,
) -> PerformanceFeatures:
    stored = await repository.feature_for_snapshot(db, latest.id)
    observation_count, first_observed_at = await repository.series_extent(db, content_id)

    result = PerformanceFeatures(
        observation_count=observation_count,
        first_observed_at=as_utc(first_observed_at) if first_observed_at else None,
    )
    if stored is not None:
        # Read the stored row rather than recomputing on the fly: the
        # answer a caller gets must match what the trust engine and any
        # audit are looking at.
        result = result.model_copy(
            update={
                "incremental_views": stored.incremental_views,
                "view_velocity_per_hour": stored.view_velocity_per_hour,
                "growth_rate": stored.growth_rate,
                "like_view_ratio": stored.like_view_ratio,
                "comment_view_ratio": stored.comment_view_ratio,
                "share_view_ratio": stored.share_view_ratio,
            }
        )

    if since_snapshot_id is not None:
        baseline = await db.get(MetricSnapshot, since_snapshot_id)
        # A baseline from a different post would silently produce a
        # nonsense figure, so an unusable one yields null rather than a
        # number nobody should trust.
        if baseline is not None and baseline.content_id == content_id:
            result = result.model_copy(
                update={"billable_views": features.billable_views(latest, baseline)}
            )

    return result


async def _tracking(db: AsyncSession, content_id: uuid.UUID) -> TrackingState | None:
    tracking = await repository.tracking_for_content(db, content_id)
    if tracking is None:
        return None
    return TrackingState(
        status=tracking.status,
        reason_code=tracking.last_error_code,
        message=tracking.last_error_message,
        next_poll_at=as_utc(tracking.next_poll_at) if tracking.next_poll_at else None,
        last_success_at=as_utc(tracking.last_success_at) if tracking.last_success_at else None,
    )
