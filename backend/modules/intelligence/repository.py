"""All the SQL this module needs, and nothing else.

Kept separate from `ingestion.py` so that policy ("should we write another
snapshot?") and persistence ("write this row") never tangle. It also means
the ingestion tests can read what happened without writing queries inline.

Nothing here commits. The caller owns the transaction boundary, because
one ingest is one unit of work: a content row and its first snapshot must
land together or not at all.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ContentTracking, MetricSnapshot, SocialContent
from .scheduling import TrackingStatus


async def content_for_submission(db: AsyncSession, submission_id: uuid.UUID) -> SocialContent | None:
    return await db.scalar(
        sa.select(SocialContent).where(SocialContent.submission_id == submission_id)
    )


async def add_content(db: AsyncSession, content: SocialContent) -> SocialContent:
    db.add(content)
    # Flush rather than commit: the row gets its primary key so the first
    # snapshot can reference it, while the caller keeps the option to roll
    # the whole ingest back.
    await db.flush()
    return content


async def latest_snapshot(db: AsyncSession, content_id: uuid.UUID) -> MetricSnapshot | None:
    return await db.scalar(
        sa.select(MetricSnapshot)
        .where(MetricSnapshot.content_id == content_id)
        .order_by(MetricSnapshot.captured_at.desc())
        .limit(1)
    )


async def add_snapshot(db: AsyncSession, snapshot: MetricSnapshot) -> MetricSnapshot:
    db.add(snapshot)
    await db.flush()
    return snapshot


async def snapshots_for_content(db: AsyncSession, content_id: uuid.UUID) -> list[MetricSnapshot]:
    """Oldest first — the order every time-series calculation wants."""
    result = await db.scalars(
        sa.select(MetricSnapshot)
        .where(MetricSnapshot.content_id == content_id)
        .order_by(MetricSnapshot.captured_at.asc())
    )
    return list(result)


async def tracking_for_content(db: AsyncSession, content_id: uuid.UUID) -> ContentTracking | None:
    return await db.get(ContentTracking, content_id)


async def add_tracking(db: AsyncSession, tracking: ContentTracking) -> ContentTracking:
    db.add(tracking)
    await db.flush()
    return tracking


async def claim_due(
    db: AsyncSession,
    *,
    now: datetime,
    limit: int,
    lease: timedelta,
) -> list[uuid.UUID]:
    """Take ownership of up to `limit` submissions that are due.

    Claiming is a write, not a read: each row's `next_poll_at` is pushed
    out by `lease` before we let go of the transaction. Two things fall
    out of that. A second worker running concurrently won't pick up the
    same rows, and a worker that dies mid-poll doesn't strand its work —
    the lease simply expires and the row becomes due again. The cost is
    that a crash can lose one reading, which for a time series that's
    about to be re-read anyway is the right way round.
    """
    stmt = (
        sa.select(ContentTracking)
        .where(
            ContentTracking.status == TrackingStatus.active,
            ContentTracking.next_poll_at <= now,
        )
        .order_by(ContentTracking.next_poll_at.asc())
        .limit(limit)
    )
    # Postgres can hand concurrent workers disjoint row sets for free.
    # SQLite (tests) has no such clause and no concurrency to protect
    # against, so the lease alone carries the guarantee there.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)

    rows = list(await db.scalars(stmt))
    for row in rows:
        row.next_poll_at = now + lease
    await db.flush()
    return [row.content_id for row in rows]
