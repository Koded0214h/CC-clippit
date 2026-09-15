"""The arithmetic that becomes money, pinned down.

`derive()` is pure, so this file can state every rule as a one-line
example: what happens with one data point, with a missing metric, with a
count that went *down*, with a post that has no views yet. Those four
cases are where a naive implementation quietly produces a wrong payout.

The `FeatureService` tests then cover the two things persistence has to
get right: computing the same snapshot twice must not duplicate a row,
and a formula change must be re-appliable to history.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from modules.intelligence import repository
from modules.intelligence.features import FeatureService, billable_views, derive
from modules.intelligence.models import ContentFeature, MetricSnapshot, SocialContent

T0 = datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc)


def _snapshot(
    *,
    at: datetime,
    views: int | None = None,
    likes: int | None = None,
    comments: int | None = None,
    shares: int | None = None,
    content_id: uuid.UUID | None = None,
) -> MetricSnapshot:
    """An unsaved snapshot — `derive()` never touches the database, so its
    tests don't need one either."""
    return MetricSnapshot(
        id=uuid.uuid4(),
        content_id=content_id or uuid.uuid4(),
        captured_at=at,
        views=views,
        likes=likes,
        comments=comments,
        shares=shares,
        source="fake.api",
    )


def test_a_single_observation_yields_no_rates():
    """One point is not a trend. Reporting zero growth for a post we've
    only seen once would make a brand-new submission look like a dead one."""
    derived = derive(_snapshot(at=T0, views=1000, likes=50), None)

    assert derived.incremental_views is None
    assert derived.view_velocity_per_hour is None
    assert derived.growth_rate is None
    # Ratios only need one point, so these are available immediately.
    assert derived.like_view_ratio == 0.05


def test_growth_between_two_observations():
    previous = _snapshot(at=T0, views=1000)
    current = _snapshot(at=T0 + timedelta(hours=2), views=1500)

    derived = derive(current, previous)

    assert derived.incremental_views == 500
    assert derived.view_velocity_per_hour == 250.0, "500 views over two hours"
    assert derived.growth_rate == 0.5, "500 more on a base of 1000"


def test_velocity_is_normalised_by_the_gap_not_the_poll():
    """The same 600 new views mean very different things half an hour apart
    and twelve hours apart — and our own cadence changes that gap, so a raw
    delta would partly measure our schedule instead of the post."""
    previous = _snapshot(at=T0, views=1000)

    fast = derive(_snapshot(at=T0 + timedelta(minutes=30), views=1600), previous)
    slow = derive(_snapshot(at=T0 + timedelta(hours=12), views=1600), previous)

    assert fast.view_velocity_per_hour == 1200.0
    assert slow.view_velocity_per_hour == 50.0
    assert fast.incremental_views == slow.incremental_views == 600


def test_a_downward_revision_floors_at_zero_rather_than_going_negative():
    """Platforms purge bot views days later. A negative delta reaching the
    ledger would bill a creator backwards; the drop itself is still in the
    snapshots for Stage 5 to treat as a signal."""
    previous = _snapshot(at=T0, views=5000)
    current = _snapshot(at=T0 + timedelta(hours=1), views=4200)

    derived = derive(current, previous)

    assert derived.incremental_views == 0
    assert derived.view_velocity_per_hour == 0.0
    assert derived.growth_rate == 0.0


def test_a_metric_the_platform_never_reported_stays_null():
    """`None` means "we don't know"; `0` is a claim that nothing happened.
    Confusing the two poisons every ratio built on top."""
    previous = _snapshot(at=T0, views=1000)
    current = _snapshot(at=T0 + timedelta(hours=1), views=2000, likes=None, shares=None)

    derived = derive(current, previous)

    assert derived.incremental_views == 1000
    assert derived.like_view_ratio is None
    assert derived.share_view_ratio is None


def test_a_post_with_no_views_yet_does_not_divide_by_zero():
    """Normal for the first minutes of a post's life."""
    previous = _snapshot(at=T0, views=0)
    current = _snapshot(at=T0 + timedelta(minutes=30), views=0, likes=0)

    derived = derive(current, previous)

    assert derived.incremental_views == 0
    assert derived.growth_rate is None, "growth on a base of zero is undefined, not infinite"
    assert derived.like_view_ratio is None


def test_two_readings_at_the_same_instant_produce_no_velocity():
    """Unreachable through the normal path — snapshots are unique per
    instant — but an `inf` in the ledger's input is not an acceptable
    failure mode for an impossible case."""
    previous = _snapshot(at=T0, views=1000)
    current = _snapshot(at=T0, views=1500)

    assert derive(current, previous).view_velocity_per_hour is None


def test_billable_views_is_measured_from_a_baseline_the_caller_names():
    """The figure a billing run can retry safely: same baseline in, same
    answer out, however many times it's asked."""
    settled = _snapshot(at=T0, views=1000)
    middle = _snapshot(at=T0 + timedelta(hours=1), views=1800)
    latest = _snapshot(at=T0 + timedelta(hours=2), views=2500)

    assert billable_views(latest, settled) == 1500
    assert billable_views(latest, settled) == 1500, "asking twice must not change the answer"
    assert billable_views(middle, settled) == 800
    assert billable_views(latest, None) == 2500, "nothing settled yet means it's all outstanding"


def test_billable_views_also_refuses_to_go_negative():
    settled = _snapshot(at=T0, views=5000)
    latest = _snapshot(at=T0 + timedelta(hours=1), views=4000)

    assert billable_views(latest, settled) == 0


# --- persistence -----------------------------------------------------
async def _content(db) -> SocialContent:
    content = SocialContent(
        submission_id=uuid.uuid4(),
        campaign_id=uuid.uuid4(),
        creator_id=uuid.uuid4(),
        platform="tiktok",
        platform_content_id="7401234567890123456",
        url="https://www.tiktok.com/@creator/video/7401234567890123456",
        kind="video",
        post_type="original",
        published_at=T0 - timedelta(hours=1),
    )
    return await repository.add_content(db, content)


async def _store_series(db, content_id, points: list[tuple[datetime, int]]) -> list[MetricSnapshot]:
    stored = []
    for at, views in points:
        stored.append(
            await repository.add_snapshot(
                db, _snapshot(at=at, views=views, likes=10, content_id=content_id)
            )
        )
    return stored


async def test_features_are_stored_against_the_snapshot_they_describe(db):
    content = await _content(db)
    snapshots = await _store_series(db, content.id, [(T0, 1000), (T0 + timedelta(hours=1), 1600)])

    service = FeatureService(db)
    await service.record_for_snapshot(content.id, snapshots[0].id)
    second = await service.record_for_snapshot(content.id, snapshots[1].id)

    assert second.snapshot_id == snapshots[1].id
    assert second.incremental_views == 600
    assert second.view_velocity_per_hour == 600.0


async def test_recomputing_a_snapshot_overwrites_instead_of_duplicating(db):
    """Features are a cache of a calculation, so recomputing is expected.
    The unique constraint on `snapshot_id` is what keeps that from silently
    growing a second, conflicting answer."""
    content = await _content(db)
    snapshots = await _store_series(db, content.id, [(T0, 1000)])

    service = FeatureService(db)
    first = await service.record_for_snapshot(content.id, snapshots[0].id)
    again = await service.record_for_snapshot(content.id, snapshots[0].id)

    assert first.id == again.id
    rows = await db.scalar(sa.select(sa.func.count()).select_from(ContentFeature))
    assert rows == 1


async def test_the_whole_history_can_be_rebuilt_from_snapshots_alone(db):
    """The payoff for never touching an observation: when the formula
    changes, the past can be recalculated instead of refetched."""
    content = await _content(db)
    await _store_series(
        db,
        content.id,
        [
            (T0, 1000),
            (T0 + timedelta(hours=1), 1500),
            (T0 + timedelta(hours=2), 2100),
        ],
    )

    computed = await FeatureService(db).recompute_all(content.id)

    assert computed == 3
    rows = list(
        await db.scalars(
            sa.select(ContentFeature)
            .join(MetricSnapshot, MetricSnapshot.id == ContentFeature.snapshot_id)
            .order_by(MetricSnapshot.captured_at)
        )
    )
    assert [r.incremental_views for r in rows] == [None, 500, 600]


async def test_recompute_is_idempotent_over_the_whole_series(db):
    content = await _content(db)
    await _store_series(db, content.id, [(T0, 1000), (T0 + timedelta(hours=1), 1500)])

    service = FeatureService(db)
    await service.recompute_all(content.id)
    await service.recompute_all(content.id)

    rows = await db.scalar(sa.select(sa.func.count()).select_from(ContentFeature))
    assert rows == 2


async def test_a_backfilled_older_reading_is_compared_to_the_right_neighbour(db):
    """"Previous" means previous in the post's life, not in our insert
    order — otherwise a late-arriving reading would be diffed against the
    future."""
    content = await _content(db)
    await _store_series(db, content.id, [(T0, 1000), (T0 + timedelta(hours=2), 2000)])
    backfilled = await _store_series(db, content.id, [(T0 + timedelta(hours=1), 1400)])

    feature = await FeatureService(db).record_for_snapshot(content.id, backfilled[0].id)

    assert feature.incremental_views == 400, "compared against T0, not against T0+2h"


async def test_a_snapshot_that_does_not_exist_is_not_invented(db):
    content = await _content(db)

    assert await FeatureService(db).record_for_snapshot(content.id, uuid.uuid4()) is None
