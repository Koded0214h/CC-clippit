"""Turning counters into meaning — and into money.

This is the file the product's revenue rests on, so it's written to be
boring and obvious. `derive()` is a pure function of two snapshots; the
service around it just decides which two and where to put the answer.

Four rules run through everything here, and they're all the same rule
wearing different hats: **never invent a number.**

1. **Missing input, missing output.** If a platform didn't report views,
   velocity is `None`, not zero. Zero is a claim ("nothing happened");
   null is the truth ("we don't know").
2. **One point is not a trend.** A post's first observation has no
   previous reading to compare against, so every delta is `None`. This is
   what stops a brand-new submission looking like a dead one.
3. **Deltas are floored at zero.** Platforms revise counts *down* — bot
   purges, deleted comments, recounted views. A negative delta must never
   reach the ledger, and a subtraction nobody floored is exactly how a
   creator ends up being billed backwards.
4. **Nothing is divided by an unchecked denominator.** Every ratio and
   rate guards its divisor, because a post with zero views is normal for
   the first few minutes of its life.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from . import repository
from .models import ContentFeature, MetricSnapshot
from .timeutils import as_utc, utcnow


@dataclass(frozen=True)
class DerivedMetrics:
    """Everything one observation tells us, given the one before it."""

    incremental_views: int | None = None
    view_velocity_per_hour: float | None = None
    growth_rate: float | None = None
    like_view_ratio: float | None = None
    comment_view_ratio: float | None = None
    share_view_ratio: float | None = None


def derive(current: MetricSnapshot, previous: MetricSnapshot | None) -> DerivedMetrics:
    """Compare two observations. Pure — no clock, no database, no I/O.

    `previous` is None for a post's first-ever reading, in which case only
    the ratios (which need a single point) come back populated.
    """
    incremental_views = _delta(current.views, previous.views if previous else None)

    return DerivedMetrics(
        incremental_views=incremental_views,
        view_velocity_per_hour=_velocity(incremental_views, current, previous),
        growth_rate=_ratio(incremental_views, previous.views if previous else None),
        like_view_ratio=_ratio(current.likes, current.views),
        comment_view_ratio=_ratio(current.comments, current.views),
        share_view_ratio=_ratio(current.shares, current.views),
    )


def billable_views(current: MetricSnapshot, baseline: MetricSnapshot | None) -> int | None:
    """Views gained between two arbitrary observations, for a caller that
    knows which one it last paid for.

    Separate from `incremental_views` on purpose. That figure is relative
    to the previous *poll*, which moves every half hour — a biller summing
    it would double-count anything it read twice and miss anything it read
    late. This one is relative to a snapshot the caller names, so the same
    request asked twice gives the same answer, and "what do I owe since
    payment #4" has exactly one correct value.
    """
    if baseline is None:
        # No baseline means nothing has been settled yet, so everything
        # observed so far is outstanding.
        return current.views
    return _delta(current.views, baseline.views)


def _delta(current: int | None, previous: int | None) -> int | None:
    if current is None:
        return None
    if previous is None:
        return None
    # Rule 3: a platform revising a count downward is a real event, but it
    # is not negative earnings.
    return max(current - previous, 0)


def _velocity(
    incremental_views: int | None,
    current: MetricSnapshot,
    previous: MetricSnapshot | None,
) -> float | None:
    """Views per hour across the gap between two readings.

    Normalizing by elapsed time is what makes the number comparable at
    all: polls land 30 minutes apart on day one and 12 hours apart in week
    three, so a raw delta says as much about our polling schedule as it
    does about the post.
    """
    if incremental_views is None or previous is None:
        return None

    elapsed = (as_utc(current.captured_at) - as_utc(previous.captured_at)).total_seconds()
    if elapsed <= 0:
        # Can't happen through the normal path (snapshots are unique per
        # instant and written in order), but dividing by zero here would
        # put an `inf` into the ledger's input.
        return None
    return incremental_views / (elapsed / 3600)


def _ratio(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or not denominator or denominator <= 0:
        return None
    return numerator / denominator


class FeatureService:
    """Persists derived values, and can throw them all away and rebuild.

    Takes a session it doesn't own, like `IngestionService` — the caller
    decides the transaction, because deriving features is part of the same
    unit of work as recording the observation they came from.
    """

    def __init__(self, db: AsyncSession, *, clock=utcnow) -> None:
        self._db = db
        self._clock = clock

    async def record_for_snapshot(
        self, content_id: uuid.UUID, snapshot_id: uuid.UUID
    ) -> ContentFeature | None:
        """Derive and store the features for one observation.

        Idempotent: called twice for the same snapshot, it overwrites the
        row rather than adding a second. Overwriting is safe here in a way
        it never is for a snapshot — this table is a cache of a
        calculation, not a record of something that happened.
        """
        snapshot = await self._db.get(MetricSnapshot, snapshot_id)
        if snapshot is None:
            return None

        previous = await repository.snapshot_before(self._db, content_id, snapshot.captured_at)
        return await self._upsert(content_id, snapshot, previous, self._clock())

    async def recompute_all(self, content_id: uuid.UUID) -> int:
        """Rebuild every feature row for one post from its snapshots.

        This is the method that makes rule "features are recomputable"
        mean something. When the velocity formula changes, or a bug is
        found in it, this walks the untouched history and produces a
        corrected series — no re-fetching from any platform, no lost data.
        """
        series = await repository.snapshots_for_content(self._db, content_id)
        computed_at = self._clock()

        previous: MetricSnapshot | None = None
        for snapshot in series:
            await self._upsert(content_id, snapshot, previous, computed_at)
            previous = snapshot
        return len(series)

    async def _upsert(
        self,
        content_id: uuid.UUID,
        snapshot: MetricSnapshot,
        previous: MetricSnapshot | None,
        computed_at: datetime,
    ) -> ContentFeature:
        derived = derive(snapshot, previous)
        existing = await repository.feature_for_snapshot(self._db, snapshot.id)

        if existing is not None:
            for field, value in asdict(derived).items():
                setattr(existing, field, value)
            existing.computed_at = computed_at
            await self._db.flush()
            return existing

        return await repository.add_feature(
            self._db,
            ContentFeature(
                content_id=content_id,
                snapshot_id=snapshot.id,
                computed_at=computed_at,
                **asdict(derived),
            ),

            # It might look a little bit different.
            # I need to work   
        )
