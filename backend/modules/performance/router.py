from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.deps import get_db
from core.internal_client import get_internal_client
from modules.auth.deps import get_current_user, get_verified_user
from modules.auth.models import Role, User
from modules.campaigns import models, schemas, service as campaign_service
from modules.earnings.models import EarningEntry
from modules.earnings import service as earnings_service
from modules.submissions.models import Submission

from . import service

router = APIRouter(tags=["performance"])


async def _campaign(ref: str, db: AsyncSession) -> models.Campaign:
    campaign = await campaign_service.resolve(db, ref)
    if campaign is None:
        raise HTTPException(404, "Campaign not found")
    return campaign


@router.post("/campaigns/{campaign_ref}/attribution-links", response_model=schemas.AttributionLinkOut)
async def create_attribution_link(
    campaign_ref: str,
    payload: schemas.AttributionLinkCreate,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != Role.creator:
        raise HTTPException(403, "Only creators can create campaign links")
    campaign = await _campaign(campaign_ref, db)
    if not campaign.conversion_destination_url:
        raise HTTPException(409, "This campaign does not track off-platform conversions")
    joined = await db.scalar(
        select(models.CampaignMembership.id).where(
            models.CampaignMembership.campaign_id == campaign.id,
            models.CampaignMembership.creator_id == user.id,
            models.CampaignMembership.left_at.is_(None),
        )
    )
    submission = None
    if payload.submission_id:
        submission = await db.get(Submission, payload.submission_id)
        if submission is None or submission.creator_id != user.id or submission.campaign_id != campaign.id:
            raise HTTPException(404, "Submission not found for this campaign")
    else:
        submission = await db.scalar(
            select(Submission)
            .where(Submission.creator_id == user.id, Submission.campaign_id == campaign.id)
            .order_by(Submission.created_at.desc())
            .limit(1)
        )
    if not joined and submission is None:
        raise HTTPException(409, "Join the campaign before creating a tracked link")

    token = service.new_secret("clp")
    link = models.AttributionLink(
        campaign_id=campaign.id,
        creator_id=user.id,
        submission_id=submission.id if submission else None,
        token_hash=service.digest(token),
        short_code=await service.unique_short_code(db),
        destination_url=campaign.conversion_destination_url,
        expires_at=service.link_expiry(campaign),
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return schemas.AttributionLinkOut(
        id=link.id,
        campaign_id=campaign.id,
        short_code=link.short_code,
        tracking_url=f"{get_settings().public_base_url.rstrip('/')}/t/{token}",
        destination_url=service.attributed_destination(link, campaign),
        expires_at=link.expires_at,
    )


@router.get("/t/{token}", include_in_schema=False)
async def follow_attribution_link(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    link = await db.scalar(
        select(models.AttributionLink).where(
            models.AttributionLink.token_hash == service.digest(token),
            models.AttributionLink.active.is_(True),
        )
    )
    now = datetime.now(timezone.utc)
    if link is None or (link.expires_at and link.expires_at < now):
        raise HTTPException(404, "This campaign link is no longer available")
    campaign = await db.get(models.Campaign, link.campaign_id)
    if campaign is None:
        raise HTTPException(404, "Campaign not found")

    fingerprint = service.digest(
        f"{request.client.host if request.client else ''}|{request.headers.get('user-agent', '')}|{link.id}"
    )[:24]
    recent_events = list(
        await db.scalars(
            select(models.PerformanceEvent).where(
                models.PerformanceEvent.attribution_link_id == link.id,
                models.PerformanceEvent.event_type == "visit",
                models.PerformanceEvent.occurred_at >= now - timedelta(seconds=30),
            )
        )
    )
    recent = any((event.metadata_json or {}).get("fingerprint") == fingerprint for event in recent_events)
    db.add(
        models.PerformanceEvent(
            campaign_id=campaign.id,
            creator_id=link.creator_id,
            submission_id=link.submission_id,
            attribution_link_id=link.id,
            event_type="visit",
            quantity=1,
            source="tracked_link",
            source_event_id=str(uuid.uuid4()),
            verification_status="observed" if recent else "verified",
            fraud_status="suspicious" if recent else "clear",
            metadata_json={"fingerprint": fingerprint},
            occurred_at=now,
        )
    )
    link.last_visited_at = now
    await db.commit()
    response = RedirectResponse(service.attributed_destination(link, campaign), status_code=307)
    response.set_cookie("clippit_attribution", link.short_code, max_age=campaign.attribution_window_days * 86400, httponly=True, samesite="lax", secure=True)
    return response


@router.get("/attribution/{short_code}")
async def resolve_attribution(short_code: str, db: AsyncSession = Depends(get_db)):
    link = await db.scalar(select(models.AttributionLink).where(models.AttributionLink.short_code == short_code.upper()))
    if link is None or not link.active or (link.expires_at and link.expires_at < datetime.now(timezone.utc)):
        raise HTTPException(404, "Attribution reference not found")
    return {"valid": True, "campaign_id": link.campaign_id, "expires_at": link.expires_at}


@router.post("/campaigns/{campaign_ref}/integration-secret", response_model=schemas.IntegrationSecretOut)
async def rotate_integration_secret(
    campaign_ref: str,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    campaign = await _campaign(campaign_ref, db)
    campaign_service.ensure_can_manage(campaign, user)
    secret = service.new_secret("clp_live", 32)
    integration = await db.get(models.CampaignIntegration, campaign.id)
    if integration is None:
        integration = models.CampaignIntegration(campaign_id=campaign.id, secret_hash=service.digest(secret), secret_last_four=secret[-4:])
        db.add(integration)
    else:
        integration.secret_hash = service.digest(secret)
        integration.secret_last_four = secret[-4:]
        integration.rotated_at = datetime.now(timezone.utc)
    await db.commit()
    return schemas.IntegrationSecretOut(campaign_id=campaign.id, secret=secret, last_four=secret[-4:])


@router.post("/performance/events", response_model=schemas.PerformanceEventOut, status_code=status.HTTP_201_CREATED)
async def record_performance_event(
    payload: schemas.PerformanceEventIn,
    x_clippit_secret: str = Header(alias="X-Clippit-Secret"),
    db: AsyncSession = Depends(get_db),
    client=Depends(get_internal_client),
):
    integration = await db.get(models.CampaignIntegration, payload.campaign_id)
    if integration is None or not __import__("hmac").compare_digest(integration.secret_hash, service.digest(x_clippit_secret)):
        raise HTTPException(401, "Invalid campaign integration secret")
    link = await db.scalar(
        select(models.AttributionLink).where(
            models.AttributionLink.campaign_id == payload.campaign_id,
            models.AttributionLink.short_code == payload.attribution_code.upper(),
            models.AttributionLink.active.is_(True),
        )
    )
    if link is None:
        raise HTTPException(422, "Attribution reference is invalid for this campaign")
    if link.expires_at and link.expires_at < datetime.now(timezone.utc):
        raise HTTPException(422, "The attribution window for this reference has ended")
    selected = await db.scalar(
        select(models.CampaignMetric.id).where(
            models.CampaignMetric.campaign_id == payload.campaign_id,
            models.CampaignMetric.metric_type == payload.event_type.value,
        )
    )
    if selected is None:
        raise HTTPException(422, "This campaign does not measure that event")
    existing = await db.scalar(
        select(models.PerformanceEvent).where(
            models.PerformanceEvent.campaign_id == payload.campaign_id,
            models.PerformanceEvent.source == "brand_server",
            models.PerformanceEvent.source_event_id == payload.source_event_id,
        )
    )
    if existing:
        return _event_out(existing)
    occurred_at = payload.occurred_at or datetime.now(timezone.utc)
    event = models.PerformanceEvent(
        campaign_id=payload.campaign_id,
        creator_id=link.creator_id,
        submission_id=link.submission_id,
        attribution_link_id=link.id,
        event_type=payload.event_type.value,
        quantity=payload.quantity,
        value_amount=payload.value_amount,
        currency=payload.currency.upper() if payload.currency else None,
        source="brand_server",
        source_event_id=payload.source_event_id,
        verification_status="confirmed",
        fraud_status="suspicious" if payload.quantity > 100 else "clear",
        metadata_json=payload.metadata,
        occurred_at=occurred_at,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    if event.submission_id is not None and event.fraud_status == "clear":
        try:
            await earnings_service.settle_submission(db, event.submission_id, client)
            await db.commit()
        except earnings_service.IntelligenceUnavailable:
            # The event remains safely recorded; the normal settlement job retries.
            pass
    return _event_out(event)


def _event_out(event: models.PerformanceEvent) -> schemas.PerformanceEventOut:
    return schemas.PerformanceEventOut(
        id=event.id,
        campaign_id=event.campaign_id,
        creator_id=event.creator_id,
        submission_id=event.submission_id,
        event_type=event.event_type,
        quantity=event.quantity,
        value_amount=event.value_amount,
        currency=event.currency,
        verification_status=event.verification_status,
        occurred_at=event.occurred_at,
    )


@router.get("/campaigns/{campaign_ref}/performance", response_model=schemas.PerformanceSummaryOut)
async def campaign_performance(
    campaign_ref: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    campaign = await campaign_service.resolve(db, campaign_ref)
    if campaign is None:
        raise HTTPException(404, "Campaign not found")
    if user.role not in (Role.admin, Role.organisation, Role.creator):
        raise HTTPException(403, "Not allowed")
    if user.role == Role.organisation and campaign.event_manager_id != user.id:
        raise HTTPException(403, "Not allowed")
    creator_id = None
    if user.role == Role.creator:
        participates = await db.scalar(
            select(models.CampaignMembership.id).where(
                models.CampaignMembership.campaign_id == campaign.id,
                models.CampaignMembership.creator_id == user.id,
                models.CampaignMembership.left_at.is_(None),
            )
        )
        has_submission = await db.scalar(
            select(Submission.id).where(
                Submission.campaign_id == campaign.id,
                Submission.creator_id == user.id,
            )
        )
        if not participates and not has_submission:
            raise HTTPException(403, "Join this campaign to view its performance")
        creator_id = user.id
    totals = await service.performance_totals(db, campaign.id, creator_id=creator_id)
    earnings_query = (
        select(EarningEntry.metric_type, func.coalesce(func.sum(EarningEntry.amount), 0))
        .where(EarningEntry.campaign_id == campaign.id)
        .group_by(EarningEntry.metric_type)
    )
    if creator_id is not None:
        earnings_query = earnings_query.where(EarningEntry.creator_id == creator_id)
    earnings = {metric: amount for metric, amount in await db.execute(earnings_query)}
    rows = []
    for metric in campaign.performance_metrics:
        values = totals.get(metric.metric_type, {"approved": 0, "pending": 0})
        approved = values["approved"]
        rows.append(
            schemas.PerformanceMetricSummary(
                metric_type=metric.metric_type,
                total=approved + values["pending"],
                approved=approved,
                pending=values["pending"],
                earned=earnings.get(metric.metric_type, 0),
            )
        )
    return schemas.PerformanceSummaryOut(campaign_id=campaign.id, metrics=rows)
