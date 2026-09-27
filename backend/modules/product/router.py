"""Runtime, customer-safe config and public profiles
(production-api-inventory.md §D). Nothing here needs a session — these
are read by the marketing site, the campaign builder, and public profile
pages alike.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.deps import get_db
from core.handles import is_valid, normalize
from core.platforms import V1_PLATFORMS, Platform
from modules.auth.providers import is_connectable
from modules.campaigns.models import Campaign, CampaignStatus
from modules.campaigns.service import brands
from modules.creators.models import CreatorProfile
from modules.creators.schemas import PublicCreatorProfileOut, PublicCreatorStats, PublicCreatorWork
from modules.earnings.models import EarningAccount
from modules.legal import documents as legal_documents
from modules.organisations.models import OrganisationProfile
from modules.organisations.schemas import PublicCampaignSummary, PublicOrganisationProfileOut
from modules.submissions.models import Submission, SubmissionStatus, VerificationStatus
from modules.uploads.service import url_for_upload

from . import schemas

router = APIRouter(tags=["product"])


@router.get("/product-config", response_model=schemas.ProductConfigOut)
async def product_config():
    settings = get_settings()
    return schemas.ProductConfigOut(
        hold_days=settings.earnings_hold_days,
        min_withdrawal_naira=settings.min_withdrawal,
        funding_fee_rate=settings.funding_fee_rate,
        platforms=[
            schemas.PlatformConfig(platform=p, connectable=is_connectable(p.value))
            for p in Platform
            if p in V1_PLATFORMS
        ],
        campaign_limits=schemas.CampaignLimits(min_duration_days=1, max_duration_days=90, max_rules=20),
        upload_limits=schemas.UploadLimits(
            max_image_bytes=settings.max_image_bytes,
            max_video_bytes=settings.max_video_bytes,
            max_evidence_bytes=settings.max_evidence_bytes,
        ),
        legal=[
            schemas.LegalVersion(slug=doc.slug, version=doc.version, effective_date=doc.effective_date)
            for doc in legal_documents.REGISTRY.values()
        ],
    )


@router.get("/handles/{handle}/availability", response_model=schemas.HandleAvailabilityOut)
async def handle_availability(handle: str, db: AsyncSession = Depends(get_db)):
    """Never reveals *who* holds a taken handle — a private (or someone
    else's) account's existence isn't confirmed beyond "not available"."""
    normalized = normalize(handle)
    if not is_valid(normalized):
        return schemas.HandleAvailabilityOut(handle=normalized, available=False, reason="invalid")
    taken = await db.scalar(
        select(CreatorProfile.user_id).where(CreatorProfile.handle == normalized)
    ) or await db.scalar(select(OrganisationProfile.user_id).where(OrganisationProfile.slug == normalized))
    return schemas.HandleAvailabilityOut(handle=normalized, available=not taken, reason="taken" if taken else None)


@router.get("/profiles/creators/{handle}", response_model=PublicCreatorProfileOut)
async def public_creator_profile(handle: str, db: AsyncSession = Depends(get_db)):
    profile = await db.scalar(
        select(CreatorProfile).where(CreatorProfile.handle == normalize(handle), CreatorProfile.public_profile.is_(True))
    )
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such profile")

    approved = (
        select(Submission)
        .where(
            Submission.creator_id == profile.user_id,
            Submission.verification_status == VerificationStatus.approved,
            Submission.status == SubmissionStatus.submitted,
        )
        .order_by(Submission.created_at.desc())
    )
    rows = list(await db.scalars(approved))
    campaign_ids = {r.campaign_id for r in rows}
    campaigns = {
        c.id: c for c in await db.scalars(select(Campaign).where(Campaign.id.in_(campaign_ids)))
    } if campaign_ids else {}
    brand_map = await brands(db, {c.event_manager_id for c in campaigns.values()}) if campaigns else {}

    views_total = await db.scalar(
        select(func.coalesce(func.sum(EarningAccount.cumulative_views), 0)).where(
            EarningAccount.creator_id == profile.user_id
        )
    )

    recent_work = []
    for sub in rows[:6]:
        campaign = campaigns.get(sub.campaign_id)
        if campaign is None:
            continue
        recent_work.append(
            PublicCreatorWork(
                campaign_title=campaign.title,
                campaign_slug=campaign.slug,
                brand_name=brand_map[campaign.event_manager_id].name if campaign.event_manager_id in brand_map else None,
                platform=sub.platform,
                submitted_at=sub.created_at,
            )
        )

    return PublicCreatorProfileOut(
        handle=profile.handle,
        display_name=profile.display_name,
        photo_url=await url_for_upload(db, profile.photo_upload_id),
        bio=profile.bio,
        interests=list(profile.interests or []),
        stats=PublicCreatorStats(approved_clips=len(rows), verified_views=int(views_total or 0)),
        recent_work=recent_work,
    )


@router.get("/profiles/creators/{handle}/clips", response_model=list[PublicCreatorWork])
async def public_creator_clips(
    handle: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    profile = await db.scalar(
        select(CreatorProfile).where(CreatorProfile.handle == normalize(handle), CreatorProfile.public_profile.is_(True))
    )
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such profile")

    rows = list(
        await db.scalars(
            select(Submission)
            .where(
                Submission.creator_id == profile.user_id,
                Submission.verification_status == VerificationStatus.approved,
                Submission.status == SubmissionStatus.submitted,
            )
            .order_by(Submission.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    campaign_ids = {r.campaign_id for r in rows}
    campaigns = {
        c.id: c for c in await db.scalars(select(Campaign).where(Campaign.id.in_(campaign_ids)))
    } if campaign_ids else {}
    brand_map = await brands(db, {c.event_manager_id for c in campaigns.values()}) if campaigns else {}
    return [
        PublicCreatorWork(
            campaign_title=campaigns[r.campaign_id].title,
            campaign_slug=campaigns[r.campaign_id].slug,
            brand_name=brand_map[campaigns[r.campaign_id].event_manager_id].name
            if campaigns[r.campaign_id].event_manager_id in brand_map else None,
            platform=r.platform,
            submitted_at=r.created_at,
        )
        for r in rows
        if r.campaign_id in campaigns
    ]


@router.get("/profiles/organisations/{slug}", response_model=PublicOrganisationProfileOut)
async def public_organisation_profile(slug: str, db: AsyncSession = Depends(get_db)):
    profile = await db.scalar(
        select(OrganisationProfile).where(
            OrganisationProfile.slug == normalize(slug), OrganisationProfile.public_profile.is_(True)
        )
    )
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such profile")

    live = await db.scalar(
        select(func.count(Campaign.id)).where(
            Campaign.event_manager_id == profile.user_id, Campaign.status == CampaignStatus.active
        )
    )
    completed = await db.scalar(
        select(func.count(Campaign.id)).where(
            Campaign.event_manager_id == profile.user_id, Campaign.status == CampaignStatus.closed
        )
    )
    return PublicOrganisationProfileOut(
        slug=profile.slug,
        name=profile.name,
        photo_url=await url_for_upload(db, profile.photo_upload_id),
        bio=profile.bio,
        website=profile.website,
        business_verified=profile.business_verified,
        campaigns=PublicCampaignSummary(live_campaigns=int(live or 0), completed_campaigns=int(completed or 0)),
    )
