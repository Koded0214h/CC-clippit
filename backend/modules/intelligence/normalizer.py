"""The one place platform-shaped data becomes Clippit-shaped data.

Everything here is a pure function: dataclass in, model instance or bool
out, no database, no network, no clock. That's deliberate — this is the
layer most likely to hide a subtle mapping bug (a metric assigned to the
wrong column, a timezone dropped), and pure functions are the cheapest
possible thing to test exhaustively.

If platform weirdness ever shows up in Koded's module, this file is the
only place it could have leaked through.
"""

from __future__ import annotations

import uuid

from integrations.social.base import PlatformContent, PlatformMetrics

from .contracts import MetricsBlock, SubmissionRef
from .models import MetricSnapshot, SocialContent

#: The seven canonical counters, in one place so the mapping, the dedupe
#: comparison and any future projection can't drift apart.
COUNTER_FIELDS = ("views", "likes", "comments", "shares", "saves", "reach", "impressions")


def build_content(submission: SubmissionRef, content: PlatformContent) -> SocialContent:
    """Marry core's identifiers to the platform's description of the post."""
    return SocialContent(
        submission_id=submission.submission_id,
        campaign_id=submission.campaign_id,
        creator_id=submission.creator_id,
        platform=content.platform,
        platform_content_id=content.platform_content_id,
        # The platform's canonical URL wins over whatever the creator pasted
        # (shortened, tracking params, mobile host) — but if the platform
        # didn't give one, keep theirs so the row is still traceable.
        url=content.url or submission.url,
        author_username=content.author_username,
        kind=content.kind,
        post_type=content.post_type,
        published_at=content.published_at,
        raw_content=content.raw,
    )


def build_snapshot(content_id: uuid.UUID, metrics: PlatformMetrics, source: str) -> MetricSnapshot:
    """One observation, ready to append. `captured_at` comes from the
    observation itself, never from `now()` at write time."""
    return MetricSnapshot(
        content_id=content_id,
        captured_at=metrics.observed_at,
        views=metrics.views,
        likes=metrics.likes,
        comments=metrics.comments,
        shares=metrics.shares,
        saves=metrics.saves,
        reach=metrics.reach,
        impressions=metrics.impressions,
        source=source,
        raw_metrics=metrics.raw,
    )


def counters_match(snapshot: MetricSnapshot, metrics: PlatformMetrics) -> bool:
    """True when a fresh reading is numerically identical to a stored one.

    Used only to spot a pointless duplicate write. Note `None == None` is a
    match here, which is correct: "this platform still doesn't report saves"
    is genuinely unchanged information.
    """
    return all(
        getattr(snapshot, field) == getattr(metrics, field) for field in COUNTER_FIELDS
    )


def metrics_block(snapshot: MetricSnapshot) -> MetricsBlock:
    """Project a stored snapshot onto the public contract — drops `source`
    and `raw_metrics`, which must never cross the module boundary."""
    return MetricsBlock(**{field: getattr(snapshot, field) for field in COUNTER_FIELDS})
