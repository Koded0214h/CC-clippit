"""Evidence-based campaign trend recommendations for brands.

The first version uses recent, approved campaign submissions already observed
by Clippit's social intelligence pipeline. It deliberately returns no trend
when the sample is too small instead of presenting a guess as current data.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from modules.intelligence.models import ContentFeature, MetricSnapshot, SocialContent
from modules.organisations.models import OrganisationProfile
from modules.submissions.models import Submission, SubmissionStatus, VerificationStatus

from . import models, schemas

TREND_WINDOW_DAYS = 30
OBSERVATION_FRESHNESS_DAYS = 7
MIN_SAMPLE_SIZE = 3
MAX_RECOMMENDATIONS = 6
MAX_CONTENT_ROWS = 1000

_HASHTAG_RE = re.compile(r"(?<![\w])#([\w]{2,40})", re.UNICODE)
_IGNORED_HASHTAGS = {
    "explorepage",
    "follow",
    "foryou",
    "foryoupage",
    "fyp",
    "like",
    "tiktok",
    "trending",
    "viral",
}
_TEXT_KEYS = {"caption", "description", "message", "text", "title", "video_description"}
_NESTED_KEYS = {"data", "media", "snippet", "video"}


@dataclass(frozen=True)
class _Evidence:
    content_id: str
    views: int
    engagement_rate: float | None
    velocity_per_hour: float | None
    observed_at: datetime


@dataclass
class _Topic:
    category: str
    label: str
    hashtag: bool
    evidence: list[_Evidence] = field(default_factory=list)


def _profile_interests(profile: OrganisationProfile | None) -> list[str]:
    if profile is None:
        return []
    interests: dict[str, str] = {}
    # Content interests describe lanes the brand funds; viewing interests
    # add secondary context. Preserve that order and deduplicate both lists.
    for value in [*(profile.content_interests or []), *(profile.viewing_interests or [])]:
        cleaned = value.strip()
        if cleaned:
            interests.setdefault(cleaned.casefold(), cleaned)
    return list(interests.values())


def _texts_from_raw(value: Any, *, depth: int = 0):
    if depth > 4:
        return
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).casefold()
            if normalized_key in _TEXT_KEYS and isinstance(child, str):
                yield child[:4000]
            elif normalized_key in _NESTED_KEYS:
                yield from _texts_from_raw(child, depth=depth + 1)
    elif isinstance(value, list):
        for child in value[:20]:
            if isinstance(child, dict):
                yield from _texts_from_raw(child, depth=depth + 1)


def _topics_for_content(content: SocialContent) -> list[tuple[str, bool]]:
    tags = {
        match.casefold()
        for text in _texts_from_raw(content.raw_content or {})
        for match in _HASHTAG_RE.findall(text)
        if match.casefold() not in _IGNORED_HASHTAGS
    }
    platform = content.platform.value.replace("_", " ").title()
    kind = content.kind.value.replace("_", " ")
    topics = [(f"#{tag}", True) for tag in sorted(tags)[:5]]
    # The format signal provides a useful category-level fallback when
    # individual hashtags are too fragmented to meet the sample threshold.
    topics.append((f"{kind} on {platform}", False))
    return topics


def _campaign_idea(category: str, topic: str, hashtag: bool, goal: str | None) -> str:
    if hashtag:
        idea = (
            f"Invite creators to build an original {category} post around {topic}, "
            "show a real use case, and finish with one clear call to action."
        )
    else:
        idea = (
            f"Invite creators to make an original {topic} for {category}, "
            "opening with a strong hook and showing the product in a real use case."
        )
    if goal:
        idea += f" Keep the brief focused on the brand goal: {goal}."
    return idea


def _recommendation(
    topic: _Topic,
    campaign_goal: str | None,
) -> tuple[schemas.BrandTrendRecommendation, float] | None:
    # Each content row is unique in the source query; keep the guard here in
    # case a future join adds duplicate rows.
    evidence_by_id = {item.content_id: item for item in topic.evidence}
    evidence = list(evidence_by_id.values())
    if len(evidence) < MIN_SAMPLE_SIZE:
        return None

    views = [item.views for item in evidence]
    engagements = [item.engagement_rate for item in evidence if item.engagement_rate is not None]
    velocities = [item.velocity_per_hour for item in evidence if item.velocity_per_hour is not None]
    median_views = int(round(median(views)))
    median_engagement = median(engagements) if engagements else None
    median_velocity = median(velocities) if len(velocities) >= 2 else None
    latest_observed_at = max(item.observed_at for item in evidence)

    if median_velocity is not None:
        insight = (
            f"Recent {topic.category} posts using {topic.label} gained a median of "
            f"{median_velocity:.1f} views per hour across {len(evidence)} posts."
        )
    elif median_engagement is not None:
        insight = (
            f"Recent {topic.category} posts using {topic.label} had a median "
            f"{median_engagement:.1%} engagement rate across {len(evidence)} posts."
        )
    else:
        insight = (
            f"{topic.label} appeared in {len(evidence)} recent {topic.category} posts; "
            "there is not enough interaction data to estimate momentum yet."
        )

    recommendation = schemas.BrandTrendRecommendation(
        category=topic.category,
        topic=topic.label,
        insight=insight,
        campaign_idea=_campaign_idea(topic.category, topic.label, topic.hashtag, campaign_goal),
        sample_size=len(evidence),
        median_views=median_views,
        median_view_velocity_per_hour=(round(median_velocity, 1) if median_velocity is not None else None),
        median_engagement_rate=(round(median_engagement, 4) if median_engagement is not None else None),
        latest_observed_at=latest_observed_at,
        confidence="high" if len(evidence) >= 10 else "medium",
    )

    # Momentum leads when enough posts have multiple observations; otherwise
    # rank by engagement and then reach. Log scaling stops one viral post from
    # drowning out every other topic.
    score = (
        math.log1p(max(median_velocity, 0)) * 0.55 if median_velocity is not None else 0
    )
    score += min(median_engagement or 0, 1) * 10 * 0.30
    score += math.log1p(max(median_views, 0)) * 0.15
    return recommendation, score


async def for_organisation(
    db: AsyncSession,
    profile: OrganisationProfile | None,
    *,
    now: datetime | None = None,
) -> schemas.BrandTrendRecommendationsOut:
    generated_at = now or datetime.now(timezone.utc)
    interests = _profile_interests(profile)
    goal = profile.campaign_goal if profile else None
    message: str | None = None

    if not interests:
        message = "Select content interests in brand onboarding to get campaign trend recommendations."
        return schemas.BrandTrendRecommendationsOut(
            interests=[], campaign_goal=goal, generated_at=generated_at, recommendations=[], message=message
        )

    published_since = generated_at - timedelta(days=TREND_WINDOW_DAYS)
    observed_since = generated_at - timedelta(days=OBSERVATION_FRESHNESS_DAYS)

    normalized_interests = [interest.casefold() for interest in interests]
    candidate_content_ids = (
        sa.select(SocialContent.id)
        .join(models.Campaign, models.Campaign.id == SocialContent.campaign_id)
        .join(Submission, Submission.id == SocialContent.submission_id)
        .where(
            sa.func.lower(sa.func.trim(models.Campaign.category)).in_(normalized_interests),
            sa.func.coalesce(SocialContent.published_at, SocialContent.created_at) >= published_since,
            Submission.status == SubmissionStatus.submitted,
            Submission.verification_status == VerificationStatus.approved,
            models.Campaign.status.in_((models.CampaignStatus.active, models.CampaignStatus.closed)),
        )
    )

    ranked_snapshots = (
        sa.select(
            MetricSnapshot.id.label("snapshot_id"),
            MetricSnapshot.content_id.label("content_id"),
            MetricSnapshot.captured_at.label("observed_at"),
            MetricSnapshot.views.label("views"),
            MetricSnapshot.likes.label("likes"),
            MetricSnapshot.comments.label("comments"),
            MetricSnapshot.shares.label("shares"),
            sa.func.row_number()
            .over(
                partition_by=MetricSnapshot.content_id,
                order_by=MetricSnapshot.captured_at.desc(),
            )
            .label("sample_rank"),
        )
        .where(
            MetricSnapshot.captured_at >= observed_since,
            MetricSnapshot.content_id.in_(candidate_content_ids),
        )
        .subquery()
    )
    latest_snapshots = (
        sa.select(ranked_snapshots)
        .where(ranked_snapshots.c.sample_rank == 1)
        .subquery()
    )
    stmt = (
        sa.select(
            SocialContent,
            models.Campaign.category,
            models.Campaign.title,
            latest_snapshots.c.observed_at,
            latest_snapshots.c.views,
            latest_snapshots.c.likes,
            latest_snapshots.c.comments,
            latest_snapshots.c.shares,
            ContentFeature.view_velocity_per_hour,
        )
        .join(models.Campaign, models.Campaign.id == SocialContent.campaign_id)
        .join(Submission, Submission.id == SocialContent.submission_id)
        .join(latest_snapshots, latest_snapshots.c.content_id == SocialContent.id)
        .outerjoin(ContentFeature, ContentFeature.snapshot_id == latest_snapshots.c.snapshot_id)
        .where(
            sa.func.lower(sa.func.trim(models.Campaign.category)).in_(normalized_interests),
            sa.func.coalesce(SocialContent.published_at, SocialContent.created_at) >= published_since,
            Submission.status == SubmissionStatus.submitted,
            Submission.verification_status == VerificationStatus.approved,
            models.Campaign.status.in_((models.CampaignStatus.active, models.CampaignStatus.closed)),
        )
        .order_by(latest_snapshots.c.observed_at.desc())
        .limit(MAX_CONTENT_ROWS)
    )
    rows = (await db.execute(stmt)).all()

    topics: dict[tuple[str, str, bool], _Topic] = {}
    for content, category, campaign_title, observed_at, views, likes, comments, shares, velocity in rows:
        # Do not let fixture/demo campaigns or missing counter data become a
        # trend signal. Other statuses are fine: a recently completed
        # campaign can still provide useful, fresh evidence.
        if re.search(r"\b(demo|test|sample)\b|latency[- ]?test|performance[- ]?test", campaign_title, re.IGNORECASE):
            continue
        if views is None or views <= 0:
            continue

        interactions = [value for value in (likes, comments, shares) if value is not None]
        engagement_rate = sum(interactions) / views if interactions else None
        evidence = _Evidence(
            content_id=str(content.id),
            views=int(views),
            engagement_rate=engagement_rate,
            velocity_per_hour=max(float(velocity), 0.0) if velocity is not None else None,
            observed_at=observed_at,
        )
        for label, hashtag in _topics_for_content(content):
            key = (category, label.casefold(), hashtag)
            topic = topics.setdefault(key, _Topic(category=category, label=label, hashtag=hashtag))
            topic.evidence.append(evidence)

    ranked: list[tuple[schemas.BrandTrendRecommendation, float]] = []
    for topic in topics.values():
        result = _recommendation(topic, goal)
        if result is not None:
            ranked.append(result)
    ranked.sort(key=lambda item: (-item[1], item[0].category.casefold(), item[0].topic.casefold()))
    recommendations = [item[0] for item in ranked[:MAX_RECOMMENDATIONS]]
    if not recommendations:
        message = (
            "There is not enough recent approved campaign performance in your selected interests yet. "
            f"Recommendations appear after at least {MIN_SAMPLE_SIZE} matching posts have fresh metrics."
        )

    return schemas.BrandTrendRecommendationsOut(
        interests=interests,
        campaign_goal=goal,
        generated_at=generated_at,
        recommendations=recommendations,
        message=message,
    )
