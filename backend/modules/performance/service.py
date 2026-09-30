from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from modules.campaigns import models


def digest(value: str) -> str:
    secret = get_settings().jwt_secret.encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()


def new_secret(prefix: str, bytes_: int = 24) -> str:
    return f"{prefix}_{secrets.token_urlsafe(bytes_)}"


async def unique_short_code(db: AsyncSession) -> str:
    while True:
        code = secrets.token_hex(5).upper()
        exists = await db.scalar(select(models.AttributionLink.id).where(models.AttributionLink.short_code == code))
        if not exists:
            return code


def attributed_destination(link: models.AttributionLink, campaign: models.Campaign) -> str:
    if campaign.conversion_destination_type == "whatsapp":
        message = f"Hello, I am interested in {campaign.title}. Clippit reference: {link.short_code}"
        return f"{link.destination_url}?{urlencode({'text': message})}"

    parts = urlsplit(link.destination_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["clippit_ref"] = link.short_code
    query["clippit_campaign"] = campaign.id.hex
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


async def performance_totals(
    db: AsyncSession, campaign_id: uuid.UUID, *, creator_id: uuid.UUID | None = None
) -> dict[str, dict[str, int]]:
    query = (
        select(
            models.PerformanceEvent.event_type,
            models.PerformanceEvent.verification_status,
            func.coalesce(func.sum(models.PerformanceEvent.quantity), 0),
        )
        .where(
            models.PerformanceEvent.campaign_id == campaign_id,
            models.PerformanceEvent.fraud_status == "clear",
        )
        .group_by(models.PerformanceEvent.event_type, models.PerformanceEvent.verification_status)
    )
    if creator_id is not None:
        query = query.where(models.PerformanceEvent.creator_id == creator_id)
    rows = await db.execute(query)
    totals: dict[str, dict[str, int]] = {}
    for metric, verification, total in rows:
        bucket = totals.setdefault(metric, {"approved": 0, "pending": 0})
        key = "approved" if verification in ("verified", "confirmed") else "pending"
        bucket[key] += int(total)
    return totals


async def record_social_snapshot(
    db: AsyncSession,
    *,
    campaign_id: uuid.UUID,
    creator_id: uuid.UUID,
    submission_id: uuid.UUID,
    snapshot_id: uuid.UUID | None,
    metrics: dict[str, int | None],
    occurred_at,
) -> None:
    """Store monotonic social deltas from an Intelligence snapshot.

    The source snapshot makes the operation idempotent. We keep deltas, not
    cumulative readings, so summaries can safely sum events.
    """
    if snapshot_id is None:
        return
    configured = set(
        await db.scalars(
            select(models.CampaignMetric.metric_type).where(models.CampaignMetric.campaign_id == campaign_id)
        )
    )
    for event_type in ("view", "comment", "share"):
        if event_type not in configured:
            continue
        current = metrics.get(f"{event_type}s")
        if current is None:
            continue
        exists = await db.scalar(
            select(models.PerformanceEvent.id).where(
                models.PerformanceEvent.campaign_id == campaign_id,
                models.PerformanceEvent.source == "platform_snapshot",
                models.PerformanceEvent.source_event_id == f"{snapshot_id}:{event_type}",
            )
        )
        if exists:
            continue
        previous = await db.scalar(
            select(func.max(models.PerformanceEvent.cumulative_total)).where(
                models.PerformanceEvent.submission_id == submission_id,
                models.PerformanceEvent.event_type == event_type,
                models.PerformanceEvent.source == "platform_snapshot",
            )
        )
        delta = max(int(current) - int(previous or 0), 0)
        if delta == 0:
            continue
        db.add(
            models.PerformanceEvent(
                campaign_id=campaign_id,
                creator_id=creator_id,
                submission_id=submission_id,
                event_type=event_type,
                quantity=delta,
                cumulative_total=int(current),
                source="platform_snapshot",
                source_event_id=f"{snapshot_id}:{event_type}",
                verification_status="verified",
                fraud_status="clear",
                occurred_at=occurred_at,
            )
        )


def link_expiry(campaign: models.Campaign):
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    natural = now + timedelta(days=campaign.attribution_window_days)
    return min(natural, campaign.ends_at + timedelta(days=campaign.attribution_window_days)) if campaign.ends_at else natural
