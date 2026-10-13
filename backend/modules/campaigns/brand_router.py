from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.deps import get_db
from core.money import ZERO, to_decimal
from modules.auth.deps import get_current_user
from modules.auth.models import Role, User
from modules.earnings.models import EarningEntry
from modules.organisations.models import OrganisationProfile
from modules.submissions.models import Submission, SubmissionStatus, VerificationStatus

from . import models, recommendations, schemas, service

router = APIRouter(prefix="/brand", tags=["brand"])


@router.get("/recommendations/trends", response_model=schemas.BrandTrendRecommendationsOut)
async def trend_recommendations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Suggest campaign angles from recent, measured posts in this brand's
    onboarding interests. No client-supplied user ID is accepted."""
    if user.role != Role.organisation:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an organisation account has this")
    profile = await db.get(OrganisationProfile, user.id)
    return await recommendations.for_organisation(db, profile)


@router.get("/overview", response_model=schemas.BrandOverviewOut)
async def overview(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """The brand home screen: what needs attention, and how the live
    campaign is doing."""
    if user.role != Role.organisation:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an organisation account has this")

    campaigns = list(
        await db.scalars(
            select(models.Campaign)
            .options(
                selectinload(models.Campaign.payout_rule),
                selectinload(models.Campaign.rules),
                selectinload(models.Campaign.performance_metrics),
            )
            .where(models.Campaign.event_manager_id == user.id)
            .order_by(models.Campaign.created_at.desc())
        )
    )
    ids = [c.id for c in campaigns]
    by_status = {s: 0 for s in models.CampaignStatus}
    for c in campaigns:
        by_status[c.status] += 1

    pending = 0
    views_24h = 0
    earnings_24h = ZERO
    spent = {}
    if ids:
        pending = await db.scalar(
            select(func.count()).select_from(Submission).where(
                Submission.campaign_id.in_(ids),
                Submission.status == SubmissionStatus.submitted,
                Submission.verification_status.in_((VerificationStatus.needs_review, VerificationStatus.appealed)),
            )
        )
        since = service.now() - timedelta(hours=24)
        row = (
            await db.execute(
                select(func.coalesce(func.sum(EarningEntry.billable_views), 0), func.coalesce(func.sum(EarningEntry.amount), 0))
                .where(EarningEntry.campaign_id.in_(ids), EarningEntry.accrued_at >= since)
            )
        ).one()
        views_24h, earnings_24h = int(row[0]), to_decimal(row[1])
        spent = await service.spent_by_campaign(db, ids)

    live = [c for c in campaigns if c.status == models.CampaignStatus.active]
    live.sort(key=lambda c: c.ends_at or c.created_at)
    featured = None
    if live:
        featured = (await service.build_outs(db, [live[0]], user))[0]

    profile = await db.get(OrganisationProfile, user.id)
    funded = [c for c in campaigns if c.status in (models.CampaignStatus.active, models.CampaignStatus.closed)]
    return schemas.BrandOverviewOut(
        organisation_name=profile.name if profile else user.full_name,
        pending_reviews=pending or 0,
        live_campaigns=by_status[models.CampaignStatus.active],
        draft_campaigns=by_status[models.CampaignStatus.draft] + by_status[models.CampaignStatus.pending_funding],
        completed_campaigns=by_status[models.CampaignStatus.closed],
        total_pot=sum((c.pot_amount for c in funded), ZERO),
        total_spent=sum((spent.get(c.id, ZERO) for c in funded), ZERO),
        views_last_24h=views_24h,
        earnings_last_24h=earnings_24h,
        unmatched_spend=ZERO,
        featured=featured,
    )
