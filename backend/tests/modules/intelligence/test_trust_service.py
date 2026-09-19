"""Storing verdicts, replaying history, and capturing labels.

The rules themselves are covered in `test_trust.py`. What's tested here is
everything around them: that a verdict is pinned to the observation that
produced it, that re-judging replaces an opinion instead of accumulating
opinions, and — the one that matters most for the modelling work ahead —
that a replay reproduces what the rules *would* have said at each point
in history without peeking at the future.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from core.platforms import Platform
from modules.intelligence import repository
from modules.intelligence.contracts import ReviewOutcome, ReviewSource, TrustStatus
from modules.intelligence.features import FeatureService
from modules.intelligence.models import MetricSnapshot, SocialContent, TrustEvaluation, TrustReview
from modules.intelligence.trust_service import TrustService, queue

T0 = datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc)


async def _content(db, *, video_id: str = "7401234567890123456") -> SocialContent:
    return await repository.add_content(
        db,
        SocialContent(
            submission_id=uuid.uuid4(),
            campaign_id=uuid.uuid4(),
            creator_id=uuid.uuid4(),
            platform=Platform.tiktok,
            platform_content_id=video_id,
            url=f"https://www.tiktok.com/@creator/video/{video_id}",
            kind="video",
            post_type="original",
            published_at=T0 - timedelta(hours=1),
        ),
    )


async def _observe(db, content, points: list[tuple[float, int]], *, likes_ratio: float = 0.06):
    """Record a history the way the pipeline would: snapshot, then
    features, in order."""
    features = FeatureService(db)
    for hours, views in points:
        snapshot = await repository.add_snapshot(
            db,
            MetricSnapshot(
                content_id=content.id,
                captured_at=T0 + timedelta(hours=hours),
                views=views,
                likes=int(views * likes_ratio),
                source="tiktok.display_api",
            ),
        )
        await features.record_for_snapshot(content.id, snapshot.id)


async def test_a_verdict_is_pinned_to_the_observation_that_produced_it(db):
    content = await _content(db)
    await _observe(db, content, [(0, 1000), (1, 1800), (2, 2500)])

    evaluation = await TrustService(db).evaluate_latest(content.id)

    latest = await repository.latest_snapshot(db, content.id)
    assert evaluation.snapshot_id == latest.id
    assert evaluation.status is TrustStatus.normal


async def test_re_judging_the_same_observation_replaces_the_opinion(db):
    """A verdict is a conclusion, not a record of something that
    happened — unlike a snapshot, overwriting it is correct."""
    content = await _content(db)
    await _observe(db, content, [(0, 1000), (1, 1800), (2, 2500)])

    service = TrustService(db)
    first = await service.evaluate_latest(content.id)
    again = await service.evaluate_latest(content.id)

    assert first.id == again.id
    count = await db.scalar(sa.select(sa.func.count()).select_from(TrustEvaluation))
    assert count == 1


async def test_replay_judges_every_point_in_history(db):
    """The backtest. New rules can be run over everything we've ever
    stored, which is the only offline evaluation available while there
    are no labels."""
    content = await _content(db)
    await _observe(db, content, [(0, 1000), (1, 1200), (2, 1400), (3, 1600), (4, 60_000)])

    evaluations = await TrustService(db).replay(content.id)

    assert len(evaluations) == 5
    statuses = [e.status for e in evaluations]
    assert statuses[0] is TrustStatus.insufficient_data, "one reading tells us nothing"
    assert statuses[-1] is TrustStatus.flagged, "the spike is visible by the last reading"


async def test_replay_never_peeks_at_the_future(db):
    """A backtest that can see later data is worthless — it would make
    every rule look prescient. Each point is judged on what existed at
    the time and nothing after it."""
    content = await _content(db)
    await _observe(db, content, [(0, 1000), (1, 1200), (2, 1400), (3, 1600), (4, 60_000)])

    evaluations = await TrustService(db).replay(content.id)

    early = evaluations[3]
    assert early.status is TrustStatus.normal, "the fourth reading was calm at the time"
    assert early.signals == []


async def test_the_stored_signal_keeps_the_threshold_it_was_judged_against(db):
    """Retuning next quarter must not silently rewrite what last
    quarter's flags meant."""
    content = await _content(db)
    await _observe(db, content, [(0, 10_000), (1, 50_000), (2, 20_000)])

    evaluation = await TrustService(db).evaluate_latest(content.id)

    assert evaluation.signals
    for signal in evaluation.signals:
        assert signal["threshold"] is not None
        assert signal["observed_value"] is not None
        assert signal["explanation"]


async def test_duplicate_submissions_are_seen_across_content_rows(db):
    """Two creators submitting the same post — the case the schema
    deliberately allows so it can be detected here."""
    first = await _content(db)
    second = await _content(db)  # same platform_content_id by default
    for content in (first, second):
        await _observe(db, content, [(0, 1000), (1, 1500), (2, 1900)])

    evaluation = await TrustService(db).evaluate_latest(second.id)

    assert "duplicate_content" in {s["code"] for s in evaluation.signals}


async def test_the_review_queue_ranks_by_score(db):
    """The composite score's only job: deciding who gets looked at first
    when there are more cases than reviewer hours."""
    calm = await _content(db, video_id="1111111111111111111")
    await _observe(db, calm, [(0, 1000), (1, 1800), (2, 2500)])
    suspicious = await _content(db, video_id="2222222222222222222")
    await _observe(db, suspicious, [(0, 40_000), (1, 200_000), (2, 60_000)], likes_ratio=0.00001)

    service = TrustService(db)
    await service.evaluate_latest(calm.id)
    await service.evaluate_latest(suspicious.id)

    ranked = await queue(db)

    assert ranked, "something should be in the queue"
    assert ranked[0].content_id == suspicious.id


async def test_a_review_keeps_the_evidence_that_produced_it(db):
    """Every label has to carry the evaluation the reviewer was looking
    at, or it's a label with no features attached."""
    content = await _content(db)
    await _observe(db, content, [(0, 40_000), (1, 200_000), (2, 60_000)], likes_ratio=0.00001)
    evaluation = await TrustService(db).evaluate_latest(content.id)

    review = await repository.add_review(
        db,
        TrustReview(
            content_id=content.id,
            evaluation_id=evaluation.id,
            outcome=ReviewOutcome.fraudulent,
            source=ReviewSource.flagged_queue,
            reviewer_id=uuid.uuid4(),
        ),
    )

    assert review.evaluation_id == evaluation.id


async def test_an_audit_review_can_exist_without_any_flag(db):
    """The selection-bias fix: reviewing content we called normal is the
    only way to ever estimate what we're missing."""
    content = await _content(db)
    await _observe(db, content, [(0, 1000), (1, 1800), (2, 2500)])
    evaluation = await TrustService(db).evaluate_latest(content.id)
    assert evaluation.status is TrustStatus.normal

    review = await repository.add_review(
        db,
        TrustReview(
            content_id=content.id,
            evaluation_id=evaluation.id,
            outcome=ReviewOutcome.legitimate,
            source=ReviewSource.random_audit,
            reviewer_id=uuid.uuid4(),
        ),
    )

    assert review.source is ReviewSource.random_audit
