"""What the Intelligence module promises the rest of Clippit.

Everything Koded's core backend ever sees from this module is one of the
models below. He never imports an adapter, never sees a provider payload,
and never needs to know whether a number came from TikTok's Display API
or a third-party reader. Equally, nothing in here knows about bank
accounts, transfers, or the ledger.

Two layers of types exist, deliberately:

- `integrations/social/base.py` holds *platform-shaped* dataclasses —
  plain, dependency-free, easy to build inside an adapter and assert on in
  a test.
- this file holds *Clippit-shaped* Pydantic models — validated and
  serialized, because these cross a module boundary as JSON.

The normalizer (Stage 2) is the only code that turns the first into the
second, which is what keeps the platform differences from leaking upward.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from core.platforms import Platform
from integrations.social.base import ContentKind, PostType

from .scheduling import TrackingStatus


class SubmissionRef(BaseModel):
    """The input side of the boundary: what core hands us to work on.

    Submissions are Koded's table, not ours. We hold the ID and re-read it
    through an interface rather than joining across domains — which also
    means Stage 2 can run against a stub while his module is still being
    built.
    """

    submission_id: uuid.UUID
    campaign_id: uuid.UUID
    creator_id: uuid.UUID
    platform: Platform
    url: str


class ContentIdentity(BaseModel):
    """Which real-world post a result is about. Carried on every response
    so a disputed number can always be traced back to a specific post."""

    platform: Platform
    platform_content_id: str
    url: str
    author_username: str | None = None
    kind: ContentKind = ContentKind.unknown
    post_type: PostType = PostType.original
    published_at: datetime | None = None


class MetricsBlock(BaseModel):
    """Cumulative totals from the most recent snapshot.

    Every field is optional because platforms differ, and `None` means
    "this platform doesn't report it" — never "it is zero". Consumers must
    handle null rather than assume a number.
    """

    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None
    reach: int | None = None
    impressions: int | None = None


class PerformanceFeatures(BaseModel):
    """Derived values, computed from at least two snapshots.

    Both view deltas are floored at zero. Platforms genuinely revise counts
    downward — TikTok prunes bot views days later — and a negative delta
    must never become a negative payout. The drop itself isn't lost: it's
    still visible in the raw snapshots, where Stage 5 can treat it as the
    trust signal it is.
    """

    #: Views gained since the *previous observation*. This is a velocity
    #: input, not a billing figure: it changes every poll, so summing it
    #: across arbitrary reads would double-count. Use `billable_views`.
    incremental_views: int | None = None
    #: Views gained since a caller-nominated snapshot — "how much has this
    #: earned since the last time I paid for it". Only populated when the
    #: caller passes `since_snapshot_id`, because only the caller knows
    #: what it has already settled. See decision D18.
    billable_views: int | None = None
    view_velocity_per_hour: float | None = None
    growth_rate: float | None = None
    like_view_ratio: float | None = None
    comment_view_ratio: float | None = None
    share_view_ratio: float | None = None
    observation_count: int = 0
    first_observed_at: datetime | None = None


class Provenance(BaseModel):
    """Where a number came from. Section 18 of the implementation plan
    makes this non-negotiable: no observation without its origin."""

    platform: Platform
    source: str = Field(description="The concrete API that answered, e.g. 'tiktok.display_api'")
    snapshot_id: uuid.UUID | None = None
    observed_at: datetime


class TrackingState(BaseModel):
    """Whether we're still watching this submission, and if not, why.

    Without this, a submission whose post went private just quietly stops
    producing new numbers and nobody upstream knows the difference between
    "no growth" and "we've stopped looking". `reason_code` is the stable
    identifier from `scheduling.decide()` — `content_unavailable`,
    `creator_reconnect_required`, `tracking_window_elapsed`, and so on.
    """

    status: TrackingStatus
    reason_code: str | None = None
    message: str | None = None
    next_poll_at: datetime | None = None
    last_success_at: datetime | None = None


class PerformanceResult(BaseModel):
    """Answer to: how is this submission actually doing?"""

    submission_id: uuid.UUID
    content: ContentIdentity
    metrics: MetricsBlock
    features: PerformanceFeatures
    provenance: Provenance
    tracking: TrackingState | None = None


class TrustStatus(str, enum.Enum):
    """Deliberately not a boolean. Most content is fine, some warrants a
    look, a little should block payment — and "we don't know yet" is a
    real, common state that must not be confused with "clean"."""

    normal = "normal"
    watch = "watch"
    flagged = "flagged"
    insufficient_data = "insufficient_data"


class SignalSeverity(str, enum.Enum):
    info = "info"
    warn = "warn"
    critical = "critical"


class ReviewOutcome(str, enum.Enum):
    """What a human concluded about a submission. These are the labels a
    supervised model will eventually train on, which is the real reason
    the review queue exists at all."""

    legitimate = "legitimate"
    fraudulent = "fraudulent"
    inconclusive = "inconclusive"


class ReviewSource(str, enum.Enum):
    """Why this submission reached a reviewer — the most important field
    in the review table.

    If humans only ever review what we flagged, every label is
    conditioned on our own detector: precision becomes measurable, recall
    never does, and a model trained on those labels learns to imitate our
    rules rather than to find fraud. A steady trickle of `random_audit`
    reviews on *unflagged* submissions is the only thing that gives an
    unbiased view of what we're missing. It looks like wasted reviewer
    time; it is the difference between having a dataset and having a
    mirror.
    """

    flagged_queue = "flagged_queue"
    random_audit = "random_audit"
    dispute = "dispute"


class TrustReviewIn(BaseModel):
    """A human's verdict, recorded against the evaluation they were
    looking at — so a label always keeps the evidence that produced it."""

    outcome: ReviewOutcome
    source: ReviewSource
    reviewer_id: uuid.UUID
    notes: str | None = None


class TrustSignal(BaseModel):
    """One reason, in a form a human can argue with.

    A score alone is unusable in a dispute — an admin needs to see which
    rule fired, on what value, against what threshold. Storing the
    threshold with the signal also means an old decision stays readable
    after the thresholds are retuned.
    """

    code: str = Field(description="Stable identifier, e.g. 'view_velocity_spike'")
    severity: SignalSeverity
    explanation: str
    observed_value: float | None = None
    threshold: float | None = None


class TrustResult(BaseModel):
    """Answer to: does this performance look credible?

    Note what is *absent*: any notion of money, approval, or payout. This
    module states what it sees. Whether that blocks a payment is the
    earnings/admin domain's decision.
    """

    submission_id: uuid.UUID
    status: TrustStatus
    anomaly_score: float = Field(ge=0.0, le=1.0)
    signals: list[TrustSignal] = Field(default_factory=list)
    evaluated_at: datetime
    #: How many comments the verdict was allowed to see. Zero on TikTok
    #: (no text API) and on any post we have not sampled yet — not the
    #: same as "the thread is empty".
    comments_sampled: int = 0


class IntelligenceResult(BaseModel):
    """Both halves together — the shape sketched in section 17 of the
    implementation plan, for callers that want one round trip."""

    submission_id: uuid.UUID
    platform: Platform
    metrics: MetricsBlock
    features: PerformanceFeatures
    trust: TrustResult
    provenance: Provenance
