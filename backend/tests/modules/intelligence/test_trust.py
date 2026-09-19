"""Every trust rule, stated as the scenario it exists to catch — and, just
as importantly, the innocent scenario it must not catch.

Each rule gets a pair: the fraud it should see, and the legitimate
behaviour that superficially resembles it. With no labels to validate
against, those false-positive tests are the closest thing we have to a
precision measurement, and a false positive here means an honest
creator's money is held up.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from core.platforms import Platform
from modules.intelligence.contracts import SignalSeverity, TrustStatus
from modules.intelligence.models import ContentFeature, MetricSnapshot
from modules.intelligence.trust import DEFAULT_THRESHOLDS, TrustInput, evaluate

T0 = datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc)


def _series(
    points: list[tuple[float, int]],
    *,
    likes_ratio: float = 0.06,
    platform: Platform = Platform.tiktok,
) -> TrustInput:
    """Build a post's history from (hours since T0, cumulative views).

    Velocities are derived exactly as `features.py` would, so these
    fixtures can't drift from what the pipeline actually stores.
    """
    snapshots: list[MetricSnapshot] = []
    features: list[ContentFeature] = []
    content_id = uuid.uuid4()

    previous: MetricSnapshot | None = None
    for hours, views in points:
        snapshot = MetricSnapshot(
            id=uuid.uuid4(),
            content_id=content_id,
            captured_at=T0 + timedelta(hours=hours),
            views=views,
            likes=int(views * likes_ratio),
            source="fake.api",
        )
        snapshots.append(snapshot)

        velocity = None
        if previous is not None and previous.views is not None:
            elapsed = (snapshot.captured_at - previous.captured_at).total_seconds() / 3600
            velocity = max(views - previous.views, 0) / elapsed if elapsed else None
        features.append(
            ContentFeature(
                id=uuid.uuid4(),
                content_id=content_id,
                snapshot_id=snapshot.id,
                computed_at=snapshot.captured_at,
                view_velocity_per_hour=velocity,
            )
        )
        previous = snapshot

    return TrustInput(platform=platform, snapshots=snapshots, features=features)


def _codes(verdict) -> set[str]:
    return {s.code for s in verdict.signals}


# --- steady, honest growth -------------------------------------------
def test_an_ordinary_post_raises_nothing():
    """The baseline that matters most. A detector that can't stay quiet
    on normal content is worse than no detector."""
    verdict = evaluate(_series([(0, 1000), (1, 1800), (2, 2500), (3, 3100), (4, 3600)]))

    assert verdict.signals == []
    assert verdict.status is TrustStatus.normal
    assert verdict.anomaly_score == 0.0


def test_a_genuinely_viral_post_is_not_punished_for_being_popular():
    """Fast but consistent growth is what success looks like. Thresholds
    compare a post against its own history rather than a global average
    precisely so a big creator isn't flagged every single time."""
    verdict = evaluate(_series([(0, 50_000), (1, 140_000), (2, 260_000), (3, 390_000)]))

    assert "view_velocity_spike" not in _codes(verdict)
    assert verdict.status in (TrustStatus.normal, TrustStatus.insufficient_data)


# --- velocity ---------------------------------------------------------
def test_a_sudden_spike_against_the_posts_own_history_is_caught():
    verdict = evaluate(_series([(0, 1000), (1, 1200), (2, 1400), (3, 1600), (4, 60_000)]))

    assert "view_velocity_spike" in _codes(verdict)
    assert verdict.status is TrustStatus.flagged


def test_small_numbers_do_not_produce_big_ratios():
    """Going from 2 views an hour to 40 is a 20x jump and means nothing.
    Without the absolute floor this rule would fire on every quiet post
    that got a single share."""
    verdict = evaluate(_series([(0, 10), (1, 12), (2, 14), (3, 16), (4, 56)]))

    assert "view_velocity_spike" not in _codes(verdict)


def test_a_post_that_was_dead_and_came_back_is_worth_a_look():
    """Legitimate causes exist — a big account reposting — so this warns
    rather than flags."""
    verdict = evaluate(
        _series([(0, 5000), (24, 5001), (48, 5002), (72, 5003), (96, 25_000)])
    )

    assert "growth_after_dormancy" in _codes(verdict)
    assert verdict.status is TrustStatus.watch


# --- the platform disagreeing with itself -----------------------------
def test_views_being_revised_downward_is_caught():
    """The strongest signal we have, and we only have it because
    snapshots are never overwritten: the platform purging views means it
    detected something we should have."""
    verdict = evaluate(_series([(0, 10_000), (1, 50_000), (2, 20_000)]))

    assert "view_count_decreased" in _codes(verdict)
    assert verdict.status is TrustStatus.flagged


def test_a_trivial_downward_correction_is_ignored():
    """Platforms wobble by a few views constantly. Flagging that would
    bury the real purges in noise."""
    verdict = evaluate(_series([(0, 10_000), (1, 12_000), (2, 11_990)]))

    assert "view_count_decreased" not in _codes(verdict)


def test_a_purge_is_reported_once_not_once_per_poll():
    """An admin needs the strongest piece of evidence, not the same
    finding repeated for every reading that followed it."""
    verdict = evaluate(_series([(0, 10_000), (1, 40_000), (2, 15_000), (3, 14_000)]))

    drops = [s for s in verdict.signals if s.code == "view_count_decreased"]
    assert len(drops) == 1


# --- engagement -------------------------------------------------------
def test_many_views_with_almost_no_likes_is_caught():
    """Views are cheap to buy; a plausible engagement profile is not.
    This is the highest value-per-effort rule in the set."""
    verdict = evaluate(
        _series([(0, 40_000), (1, 80_000), (2, 120_000)], likes_ratio=0.0002)
    )

    assert "engagement_absent" in _codes(verdict)
    assert verdict.status is TrustStatus.flagged


def test_low_engagement_on_a_small_post_is_not_evidence():
    """A few hundred views is too small a sample to conclude anything
    from — the ratio is noise at that scale."""
    verdict = evaluate(_series([(0, 100), (1, 300), (2, 600)], likes_ratio=0.0))

    assert "engagement_absent" not in _codes(verdict)


def test_engagement_far_above_the_view_count_is_caught():
    """The mirror image: buying likes instead of views."""
    verdict = evaluate(_series([(0, 5000), (1, 8000), (2, 12_000)], likes_ratio=0.9))

    assert "engagement_implausibly_high" in _codes(verdict)


def test_a_platform_that_reports_no_likes_yields_no_engagement_verdict():
    """Absence of evidence. Inferring fraud from a metric the platform
    simply doesn't expose would flag entire platforms at once."""
    inp = _series([(0, 40_000), (1, 80_000), (2, 120_000)])
    for snapshot in inp.snapshots:
        snapshot.likes = None

    assert "engagement_absent" not in _codes(evaluate(inp))


def test_engagement_bands_are_per_platform():
    """X posts sit at far lower like-to-view ratios than TikTok. One
    global threshold would flag a whole platform or miss another."""
    ratio = 0.003
    tiktok = evaluate(_series([(0, 40_000), (1, 80_000), (2, 120_000)], likes_ratio=ratio))
    x = evaluate(
        _series(
            [(0, 40_000), (1, 80_000), (2, 120_000)], likes_ratio=ratio, platform=Platform.x
        )
    )

    assert "engagement_absent" in _codes(tiktok)
    assert "engagement_absent" not in _codes(x)


# --- cross-entity -----------------------------------------------------
def test_the_same_post_submitted_twice_is_visible():
    """The schema deliberately permits the duplicate row so that it shows
    up here as evidence instead of as a rejected insert nobody sees."""
    inp = _series([(0, 1000), (1, 1500), (2, 1900)])
    duplicated = TrustInput(
        platform=inp.platform,
        snapshots=inp.snapshots,
        features=inp.features,
        duplicate_submissions=2,
    )

    verdict = evaluate(duplicated)

    assert "duplicate_content" in _codes(verdict)
    assert verdict.status is TrustStatus.watch


# --- composition ------------------------------------------------------
def test_too_little_history_says_so_rather_than_saying_clean():
    """"We don't know yet" is a real state. Defaulting a brand-new post to
    normal would make "get paid before there's enough history" the
    cheapest attack available."""
    verdict = evaluate(_series([(0, 1000), (1, 1500)]))

    assert verdict.status is TrustStatus.insufficient_data


def test_hard_evidence_outranks_a_short_history():
    """A two-reading post whose views were just purged is flagged, not
    excused for being new."""
    verdict = evaluate(_series([(0, 80_000), (1, 20_000)]))

    assert verdict.status is TrustStatus.flagged
    assert "view_count_decreased" in _codes(verdict)


def test_one_critical_signal_is_not_averaged_away_by_clean_checks():
    """The trap this design avoids: a submission with one decisive finding
    and nine passes must not come out looking fine."""
    verdict = evaluate(_series([(0, 1000), (1, 1200), (2, 1400), (3, 1600), (4, 60_000)]))

    criticals = [s for s in verdict.signals if s.severity is SignalSeverity.critical]
    assert criticals
    assert verdict.status is TrustStatus.flagged


def test_the_score_is_bounded_so_it_can_rank_a_queue():
    verdict = evaluate(
        _series([(0, 40_000), (1, 200_000), (2, 50_000)], likes_ratio=0.00001)
    )

    assert 0.0 <= verdict.anomaly_score <= 1.0
    assert verdict.anomaly_score > DEFAULT_THRESHOLDS.watch_score


@pytest.mark.parametrize(
    "points, likes_ratio",
    [
        ([(0, 1000), (1, 1200), (2, 1400), (3, 1600), (4, 60_000)], 0.06),
        ([(0, 40_000), (1, 80_000), (2, 120_000)], 0.0002),
        ([(0, 10_000), (1, 50_000), (2, 20_000)], 0.06),
    ],
)
def test_every_signal_can_be_explained_to_a_human(points, likes_ratio):
    """Stage 5's exit condition. A creator disputing a held payout must be
    able to be told what was seen, what it was compared against, and in
    what words."""
    verdict = evaluate(_series(points, likes_ratio=likes_ratio))

    assert verdict.signals
    for signal in verdict.signals:
        assert signal.code and signal.code.islower()
        assert signal.observed_value is not None
        assert signal.threshold is not None, "a decision without its threshold is unreadable later"
        assert len(signal.explanation) > 20
        assert signal.explanation.endswith(".")
