import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.deps import get_db
from core.internal_client import get_internal_client
from modules.auth.deps import get_current_user
from modules.auth.models import Role, User
from modules.submissions.models import Submission

from . import models, schemas

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


async def _get_campaign(campaign_id: uuid.UUID, db: AsyncSession) -> models.Campaign:
    campaign = await db.scalar(
        select(models.Campaign)
        .options(selectinload(models.Campaign.payout_rule))
        .where(models.Campaign.id == campaign_id)
    )
    if not campaign:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    return campaign


def _ensure_can_manage(campaign: models.Campaign, user: User) -> None:
    if user.role == Role.admin:
        return
    if campaign.event_manager_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the campaign's owner or an admin can do this")


def _ensure_visible(campaign: models.Campaign, user: User) -> None:
    """A draft is the event manager's working copy — visible only to its
    owner and admin, not browsable by creators or other organisations."""
    if campaign.status == models.CampaignStatus.draft and user.role != Role.admin:
        if campaign.event_manager_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")


@router.post("", response_model=schemas.CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: schemas.CampaignCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != Role.organisation:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an event manager account can create a campaign")

    campaign = models.Campaign(
        event_manager_id=user.id,
        title=payload.title,
        description=payload.description,
        expected_views=payload.expected_views,
        platforms=[p.value for p in payload.platforms],
    )
    db.add(campaign)
    await db.flush()
    db.add(models.CampaignPayoutRule(campaign_id=campaign.id, **payload.payout_rule.model_dump()))
    await db.commit()
    return await _get_campaign(campaign.id, db)


@router.get("", response_model=list[schemas.CampaignOut])
async def list_campaigns(
    status_filter: models.CampaignStatus | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """An event manager sees their own campaigns in any status. Everyone
    else (creators browsing, admin included) sees only `active` ones by
    default — a creator has no reason to see another org's drafts, and
    admin has GET /campaigns/{id} plus its own dashboard for the rest."""
    query = select(models.Campaign).options(selectinload(models.Campaign.payout_rule))

    if user.role == Role.organisation:
        query = query.where(models.Campaign.event_manager_id == user.id)
        if status_filter:
            query = query.where(models.Campaign.status == status_filter)
    else:
        query = query.where(models.Campaign.status == (status_filter or models.CampaignStatus.active))

    query = query.order_by(models.Campaign.created_at.desc())
    campaigns = await db.scalars(query)
    return list(campaigns)


@router.get("/{campaign_id}", response_model=schemas.CampaignOut)
async def get_campaign(
    campaign_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    campaign = await _get_campaign(campaign_id, db)
    _ensure_visible(campaign, user)
    return campaign


@router.patch("/{campaign_id}", response_model=schemas.CampaignOut)
async def update_campaign(
    campaign_id: uuid.UUID,
    payload: schemas.CampaignUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    campaign = await _get_campaign(campaign_id, db)
    _ensure_can_manage(campaign, user)
    if campaign.status != models.CampaignStatus.draft and user.role != Role.admin:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Only a draft campaign can be edited — activate a new one instead"
        )

    changes = payload.model_dump(exclude_unset=True)
    if "platforms" in changes:
        changes["platforms"] = [p.value if hasattr(p, "value") else p for p in changes["platforms"]]
    for field, value in changes.items():
        setattr(campaign, field, value)

    await db.commit()
    return await _get_campaign(campaign_id, db)


@router.put("/{campaign_id}/payout-rule", response_model=schemas.PayoutRuleOut)
async def set_payout_rule(
    campaign_id: uuid.UUID,
    payload: schemas.PayoutRuleIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    campaign = await _get_campaign(campaign_id, db)
    _ensure_can_manage(campaign, user)
    if campaign.status != models.CampaignStatus.draft and user.role != Role.admin:
        raise HTTPException(status.HTTP_409_CONFLICT, "Payout rule is locked once the campaign is active")

    if campaign.payout_rule:
        for field, value in payload.model_dump().items():
            setattr(campaign.payout_rule, field, value)
    else:
        db.add(models.CampaignPayoutRule(campaign_id=campaign.id, **payload.model_dump()))

    await db.commit()
    campaign = await _get_campaign(campaign_id, db)
    return campaign.payout_rule


@router.post("/{campaign_id}/activate", response_model=schemas.CampaignOut)
async def activate_campaign(
    campaign_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    campaign = await _get_campaign(campaign_id, db)
    _ensure_can_manage(campaign, user)
    if campaign.status != models.CampaignStatus.draft:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Campaign is already {campaign.status.value}")
    if not campaign.payout_rule:
        raise HTTPException(status.HTTP_409_CONFLICT, "Set a payout rule before activating this campaign")

    campaign.status = models.CampaignStatus.active
    await db.commit()
    return await _get_campaign(campaign_id, db)


@router.post("/{campaign_id}/close", response_model=schemas.CampaignOut)
async def close_campaign(
    campaign_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_internal_client),
):
    campaign = await _get_campaign(campaign_id, db)
    _ensure_can_manage(campaign, user)
    if campaign.status == models.CampaignStatus.closed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Campaign is already closed")

    campaign.status = models.CampaignStatus.closed
    submission_ids = list(
        await db.scalars(select(Submission.id).where(Submission.campaign_id == campaign_id))
    )
    await db.commit()
    for submission_id in submission_ids:
        try:
            await client.post(f"/internal/submissions/{submission_id}/tracking/stop")
        except httpx.HTTPError:
            pass
    return await _get_campaign(campaign_id, db)
