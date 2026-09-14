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

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from .models import MetricSnapshot, SocialContent


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
