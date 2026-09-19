"""Does this performance look credible?

Everything in the top half of this file is a pure function: snapshots and
features in, signals out. No database, no clock, no network. That's not
tidiness — it's what lets the whole rule set be replayed over historical
data to see what it *would* have flagged, which is the only offline
evaluation we can do while we have no labels.

Four principles, and they're the reason this is rules rather than a model:

1. **No labels exist yet.** Nobody has told us which submissions are
   fraudulent. An unsupervised model would answer "what is unusual",
   which is a different question from "what is dishonest" — a genuinely
   viral post is a massive outlier and completely legitimate.
2. **Every flag must survive a dispute.** When a creator's payout is held,
   "the model scored you 0.87" is not an answer. Each signal therefore
   carries the value observed, the threshold it was compared against, and
   a sentence a human can read aloud.
3. **The thresholds are stored with the decision.** Retuning next quarter
   must not silently rewrite the meaning of last quarter's flags.
4. **This module never decides anything about money.** It states what it
   sees. Whether that blocks a payout belongs to earnings and admin.

The thresholds below are *plausibility* guesses, not statistics — we have
no production population to take percentiles of yet. Decisions D10 and
D16 track replacing them with per-platform empirical percentiles (median
and MAD, not mean and standard deviation: the population will contain the
very thing we're detecting, and a handful of extreme fraudsters would drag
a mean until the detector stops detecting).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from core.platforms import Platform

from .contracts import ReviewOutcome, ReviewSource, SignalSeverity, TrustSignal, TrustStatus  # noqa: F401
from .models import ContentFeature, MetricSnapshot
from .timeutils import as_utc


@dataclass(frozen=True)
class Thresholds:
    """Every number the rules use, in one place, so a tuning session is a
    diff on one object and so each signal can report what it compared
    against."""

    #: Below this many observations we don't claim to know anything. Three
    #: is the minimum that gives two velocity readings to compare.
    min_observations: int = 3

    #: Velocity is only interesting once it's big enough to matter — going
    #: from 2 to 40 views an hour is 20x and means nothing.
    velocity_floor_per_hour: float = 500.0
    velocity_spike_multiple: float = 10.0
    velocity_spike_critical_multiple: float = 25.0

    #: A post that was effectively dead and then wasn't. Organic attention
    #: decays; it rarely resurrects without an external cause.
    dormant_velocity_per_hour: float = 1.0
    dormant_observations: int = 3
    revival_velocity_per_hour: float = 100.0

    #: A cumulative counter going *down* means the platform revised it —
    #: usually a bot purge. Expressed as a fraction of the previous value.
    view_drop_fraction: float = 0.02
    view_drop_critical_fraction: float = 0.15

    #: Engagement checks need enough views to be meaningful.
    engagement_min_views: int = 1000
    #: Bought views arrive without bought engagement. This is the cheapest
    #: high-value signal we have: views are easy to fake, a coherent
    #: engagement profile is expensive.
    min_like_view_ratio: dict[Platform, float] = field(
        default_factory=lambda: {
            Platform.tiktok: 0.005,
            Platform.instagram: 0.005,
            Platform.threads: 0.005,
            Platform.facebook: 0.002,
            Platform.x: 0.002,
            Platform.youtube: 0.002,
        }
    )
    #: The other direction: engagement too high for the view count suggests
    #: the *engagement* was bought instead.
    max_like_view_ratio: dict[Platform, float] = field(
        default_factory=lambda: {
            Platform.tiktok: 0.35,
            Platform.instagram: 0.30,
            Platform.threads: 0.30,
            Platform.facebook: 0.25,
            Platform.x: 0.20,
            Platform.youtube: 0.25,
        }
    )

    #: Severity weights for the composite score. Deliberately coarse: the
    #: score ranks the review queue, it does not make the decision.
    weights: dict[SignalSeverity, float] = field(
        default_factory=lambda: {
            SignalSeverity.info: 0.1,
            SignalSeverity.warn: 0.3,
            SignalSeverity.critical: 0.6,
        }
    )
    #: Score at or above this is worth a look, below it is business as usual.
    watch_score: float = 0.3


DEFAULT_THRESHOLDS = Thresholds()


@dataclass(frozen=True)
class TrustInput:
    """Everything the rules are allowed to see.

    Assembled by `TrustService` from stored rows only — the rules never
    reach for more data, so replaying them over history is guaranteed to
    reproduce what they'd have said at the time.
    """

    platform: Platform
    snapshots: list[MetricSnapshot]
    features: list[ContentFeature]
    #: How many *other* submissions point at this same post. Not a
    #: constraint violation by design (see the schema notes) — it's this.
    duplicate_submissions: int = 0


@dataclass(frozen=True)
class TrustVerdict:
    status: TrustStatus
    anomaly_score: float
    signals: list[TrustSignal]


def evaluate(inp: TrustInput, thresholds: Thresholds = DEFAULT_THRESHOLDS) -> TrustVerdict:
    """Run every rule, then compose the result."""
    signals = [
        signal
        for rule in (
            _velocity_spike,
            _growth_after_dormancy,
            _view_count_decreased,
            _engagement_absent,
            _engagement_implausibly_high,
            _duplicate_submission,
        )
        for signal in rule(inp, thresholds)
    ]
    return _compose(signals, inp, thresholds)


def _compose(
    signals: list[TrustSignal], inp: TrustInput, thresholds: Thresholds
) -> TrustVerdict:
    """Turn signals into a status and a score.

    The trap this avoids is averaging. A submission with one decisive
    critical signal and nine clean checks would average out to "fine",
    which is exactly backwards. So severities are *summed* (capped), and a
    single critical signal sets the status on its own regardless of the
    number.
    """
    score = min(1.0, sum(thresholds.weights[s.severity] for s in signals))
    has_critical = any(s.severity is SignalSeverity.critical for s in signals)

    if has_critical:
        # Checked before the insufficient-data guard on purpose: "we don't
        # have much history" must never suppress hard evidence.
        return TrustVerdict(TrustStatus.flagged, score, signals)

    if len(inp.snapshots) < thresholds.min_observations:
        # A real state, not a polite way of saying "clean". Defaulting a
        # brand-new post to normal would make "get paid before there's
        # enough history" the cheapest attack available.
        return TrustVerdict(TrustStatus.insufficient_data, score, signals)

    if score >= thresholds.watch_score:
        return TrustVerdict(TrustStatus.watch, score, signals)
    return TrustVerdict(TrustStatus.normal, score, signals)


# --- the rules --------------------------------------------------------
def _velocity_spike(inp: TrustInput, t: Thresholds) -> list[TrustSignal]:
    """Is the latest growth wildly out of line with this post's own past?

    Compared against the post's own median rather than a global average,
    because a big creator and a small one live on completely different
    scales and a shared threshold would flag the popular one every time.
    Median rather than mean because one prior spike shouldn't raise the
    bar for detecting the next one.
    """
    velocities = [f.view_velocity_per_hour for f in inp.features if f.view_velocity_per_hour is not None]
    if len(velocities) < 3:
        return []

    latest = velocities[-1]
    baseline = statistics.median(velocities[:-1])
    if latest < t.velocity_floor_per_hour:
        # Small numbers produce huge ratios and mean nothing.
        return []
    if baseline <= t.dormant_velocity_per_hour:
        # The post was effectively dead before this. That's a real signal,
        # but it's `_growth_after_dormancy`'s to raise — letting both rules
        # fire would count one phenomenon twice and push a warn-level
        # finding over the flag line on its own.
        return []

    multiple = latest / baseline
    if multiple < t.velocity_spike_multiple:
        return []

    critical = multiple >= t.velocity_spike_critical_multiple
    return [
        TrustSignal(
            code="view_velocity_spike",
            severity=SignalSeverity.critical if critical else SignalSeverity.warn,
            explanation=(
                f"Views grew at {latest:,.0f}/hour, {multiple:.1f}x this post's median "
                f"of {baseline:,.0f}/hour across {len(velocities)} readings."
            ),
            observed_value=round(multiple, 2),
            threshold=(
                t.velocity_spike_critical_multiple if critical else t.velocity_spike_multiple
            ),
        )
    ]


def _growth_after_dormancy(inp: TrustInput, t: Thresholds) -> list[TrustSignal]:
    """A post that was dead and came back.

    Organic attention decays. A flat stretch followed by a surge usually
    means something external happened — which can be legitimate (a repost
    by a big account) but is also exactly what buying views late in a
    campaign looks like. Worth a look, never a flag on its own.
    """
    velocities = [f.view_velocity_per_hour for f in inp.features if f.view_velocity_per_hour is not None]
    if len(velocities) <= t.dormant_observations:
        return []

    latest = velocities[-1]
    preceding = velocities[-(t.dormant_observations + 1) : -1]
    if latest < t.revival_velocity_per_hour:
        return []
    if any(v > t.dormant_velocity_per_hour for v in preceding):
        return []

    return [
        TrustSignal(
            code="growth_after_dormancy",
            severity=SignalSeverity.warn,
            explanation=(
                f"Effectively no growth across the previous {len(preceding)} readings, then "
                f"{latest:,.0f} views/hour."
            ),
            observed_value=round(latest, 2),
            threshold=t.revival_velocity_per_hour,
        )
    ]


def _view_count_decreased(inp: TrustInput, t: Thresholds) -> list[TrustSignal]:
    """The platform took views away.

    One of the strongest signals in the system, and we only have it
    because snapshots are never overwritten — the derived features floor
    deltas at zero so a negative can't reach a ledger, but the raw
    observations keep the truth. A platform revising a count downward is
    usually it purging bot traffic, which means it detected something we
    should have.
    """
    signals: list[TrustSignal] = []
    for previous, current in zip(inp.snapshots, inp.snapshots[1:]):
        if previous.views is None or current.views is None or previous.views <= 0:
            continue
        if current.views >= previous.views:
            continue

        fraction = (previous.views - current.views) / previous.views
        if fraction < t.view_drop_fraction:
            continue

        critical = fraction >= t.view_drop_critical_fraction
        signals.append(
            TrustSignal(
                code="view_count_decreased",
                severity=SignalSeverity.critical if critical else SignalSeverity.warn,
                explanation=(
                    f"The platform revised views down from {previous.views:,} to "
                    f"{current.views:,} ({fraction:.1%}) at "
                    f"{as_utc(current.captured_at):%Y-%m-%d %H:%M} UTC — typically a bot purge."
                ),
                observed_value=round(fraction, 4),
                threshold=(
                    t.view_drop_critical_fraction if critical else t.view_drop_fraction
                ),
            )
        )
    # Only the worst one: an admin needs the strongest evidence, not the
    # same finding repeated for every poll it survived.
    return sorted(signals, key=lambda s: s.observed_value or 0, reverse=True)[:1]


def _engagement_absent(inp: TrustInput, t: Thresholds) -> list[TrustSignal]:
    """Lots of views, nobody reacting.

    Views are cheap to buy; a plausible engagement profile is not. This is
    the highest value-per-unit-effort rule we have.
    """
    latest = inp.snapshots[-1]
    floor = t.min_like_view_ratio.get(inp.platform)
    if floor is None or latest.views is None or latest.views < t.engagement_min_views:
        return []
    if latest.likes is None:
        # The platform doesn't report likes. Absence of evidence — say
        # nothing rather than infer everything.
        return []

    ratio = latest.likes / latest.views
    if ratio >= floor:
        return []

    critical = ratio < floor / 5
    return [
        TrustSignal(
            code="engagement_absent",
            severity=SignalSeverity.critical if critical else SignalSeverity.warn,
            explanation=(
                f"{latest.views:,} views but only {latest.likes:,} likes ({ratio:.3%}); "
                f"{inp.platform.value} posts normally sit above {floor:.1%}."
            ),
            observed_value=round(ratio, 5),
            threshold=floor / 5 if critical else floor,
        )
    ]


def _engagement_implausibly_high(inp: TrustInput, t: Thresholds) -> list[TrustSignal]:
    """The mirror image: engagement that outruns the views it came from,
    which is what buying likes rather than views looks like."""
    latest = inp.snapshots[-1]
    ceiling = t.max_like_view_ratio.get(inp.platform)
    if ceiling is None or not latest.views or latest.likes is None:
        return []
    if latest.views < t.engagement_min_views:
        return []

    ratio = latest.likes / latest.views
    if ratio <= ceiling:
        return []

    return [
        TrustSignal(
            code="engagement_implausibly_high",
            severity=SignalSeverity.warn,
            explanation=(
                f"{latest.likes:,} likes against {latest.views:,} views ({ratio:.1%}), above "
                f"the {ceiling:.0%} ceiling for {inp.platform.value}."
            ),
            observed_value=round(ratio, 4),
            threshold=ceiling,
        )
    ]


def _duplicate_submission(inp: TrustInput, t: Thresholds) -> list[TrustSignal]:
    """The same post submitted more than once.

    The schema deliberately allows this — `(platform, platform_content_id)`
    is indexed but not unique — precisely so it surfaces here as evidence
    rather than as a rejected insert nobody ever sees.
    """
    if inp.duplicate_submissions < 1:
        return []

    return [
        TrustSignal(
            code="duplicate_content",
            severity=SignalSeverity.warn,
            explanation=(
                f"This exact post is attached to {inp.duplicate_submissions} other "
                f"submission(s)."
            ),
            observed_value=float(inp.duplicate_submissions),
            threshold=1.0,
        )
    ]


def describe(thresholds: Thresholds = DEFAULT_THRESHOLDS) -> dict[str, object]:
    """The active rule set, for an admin screen or a tuning review. Cheap
    to expose and it keeps the thresholds from becoming folklore."""
    return {
        "min_observations": thresholds.min_observations,
        "velocity_spike_multiple": thresholds.velocity_spike_multiple,
        "view_drop_fraction": thresholds.view_drop_fraction,
        "min_like_view_ratio": {p.value: v for p, v in thresholds.min_like_view_ratio.items()},
        "max_like_view_ratio": {p.value: v for p, v in thresholds.max_like_view_ratio.items()},
        "watch_score": thresholds.watch_score,
    }


def signals_to_json(signals: list[TrustSignal]) -> list[dict]:
    """Stored verbatim on the evaluation row, thresholds included, so an
    old decision stays readable after the thresholds move."""
    return [s.model_dump(mode="json") for s in signals]
