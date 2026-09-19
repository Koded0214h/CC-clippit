"""Creator submits a link against an active campaign. This module owns the
submission's own lifecycle only — performance and trust are never copied
onto it, they're read live from Intelligence's internal API every time,
via `core.internal_client` (an in-process ASGI call that exercises the
real `/internal/*` contract, X-Internal-Secret included, so nothing here
changes the day that module becomes a separate deployable).
"""

import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from core.internal_client import get_internal_client
from modules.auth.deps import get_current_user
from modules.auth.models import Platform as AuthPlatform
from modules.auth.models import Role, SocialAccount, User
from modules.campaigns.models import Campaign, CampaignStatus
from modules.intelligence.contracts import PerformanceResult, SubmissionRef

from . import models, schemas

router = APIRouter(prefix="/submissions", tags=["submissions"])


async def _get_visible_submission(submission_id: uuid.UUID, user: User, db: AsyncSession) -> models.Submission:
    """404, not 403, when the submission exists but isn't this user's to
    see — same reasoning as campaigns: don't confirm existence to someone
    who isn't entitled to know about it."""
    not_found = HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    submission = await db.get(models.Submission, submission_id)
    if not submission:
        raise not_found
    if user.role == Role.admin:
        return submission
    if user.role == Role.creator:
        if submission.creator_id != user.id:
            raise not_found
        return submission
    if user.role == Role.organisation:
        campaign = await db.get(Campaign, submission.campaign_id)
        if not campaign or campaign.event_manager_id != user.id:
            raise not_found
        return submission
    raise not_found


@router.post("", response_model=schemas.SubmissionOut, status_code=status.HTTP_201_CREATED)
async def create_submission(
    payload: schemas.SubmissionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_internal_client),
):
    if user.role != Role.creator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a creator account can submit content")

    campaign = await db.get(Campaign, payload.campaign_id)
    if not campaign or campaign.status != CampaignStatus.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found or not accepting submissions")
    if payload.platform.value not in campaign.platforms:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"This campaign doesn't accept {payload.platform.value} submissions",
        )

    has_account = (
        await db.scalar(
            select(SocialAccount.id).where(
                SocialAccount.user_id == user.id,
                SocialAccount.platform == AuthPlatform(payload.platform.value),
            )
        )
        is not None
    )
    if not has_account:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Connect your {payload.platform.value} account from your profile before submitting",
        )

    submission = models.Submission(
        campaign_id=campaign.id,
        creator_id=user.id,
        platform=payload.platform.value,
        url=payload.url,
    )
    db.add(submission)
    await db.flush()  # assigns submission.id (client-side default) before we reference it below

    ref = SubmissionRef(
        submission_id=submission.id,
        campaign_id=campaign.id,
        creator_id=user.id,
        platform=payload.platform,
        url=payload.url,
    )
    try:
        resp = await client.post(f"/internal/submissions/{submission.id}/metrics", json=ref.model_dump(mode="json"))
    except httpx.HTTPError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Could not reach the performance tracking service"
        ) from exc

    if resp.status_code >= 400:
        detail = resp.json().get("detail")
        code = detail.get("code", "unknown_error") if isinstance(detail, dict) else "unknown_error"
        message = detail.get("message") if isinstance(detail, dict) else str(detail)
        submission.status = models.SubmissionStatus.rejected
        submission.rejection_code = code
        submission.rejection_message = message
        await db.commit()
        raise HTTPException(resp.status_code, detail)

    await db.commit()
    await db.refresh(submission)
    return submission


@router.get("", response_model=list[schemas.SubmissionOut])
async def list_submissions(
    campaign_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Creator: own submissions. Organisation: submissions against its own
    campaigns. Admin: everything. Same three-way split as campaigns."""
    query = select(models.Submission)
    if user.role == Role.creator:
        query = query.where(models.Submission.creator_id == user.id)
    elif user.role == Role.organisation:
        query = query.join(Campaign, Campaign.id == models.Submission.campaign_id).where(
            Campaign.event_manager_id == user.id
        )
    if campaign_id:
        query = query.where(models.Submission.campaign_id == campaign_id)
    query = query.order_by(models.Submission.created_at.desc())
    return list(await db.scalars(query))


@router.get("/{submission_id}", response_model=schemas.SubmissionOut)
async def get_submission(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_visible_submission(submission_id, user, db)


@router.post("/{submission_id}/withdraw", response_model=schemas.SubmissionOut)
async def withdraw_submission(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_internal_client),
):
    """Withdraw locally and tell Intelligence to stop polling (D17)."""
    submission = await _get_visible_submission(submission_id, user, db)
    if user.role == Role.creator and submission.creator_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your submission")
    if user.role == Role.organisation:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the creator or an admin can withdraw a submission")
    if submission.status != models.SubmissionStatus.submitted:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Submission is already {submission.status.value}")

    submission.status = models.SubmissionStatus.withdrawn
    await db.commit()
    try:
        await client.post(f"/internal/submissions/{submission_id}/tracking/stop")
    except httpx.HTTPError:
        # The row is withdrawn either way; the 30-day cap is the backstop
        # if this call misses.
        pass
    return submission


@router.get("/{submission_id}/performance", response_model=PerformanceResult)
async def get_submission_performance(
    submission_id: uuid.UUID,
    since_snapshot_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_internal_client),
):
    """A thin, visibility-checked proxy onto Intelligence's own read
    endpoint — this module never stores or recomputes performance itself."""
    await _get_visible_submission(submission_id, user, db)

    params = {"since_snapshot_id": str(since_snapshot_id)} if since_snapshot_id else {}
    resp = await client.get(f"/internal/submissions/{submission_id}/performance", params=params)
    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, resp.json().get("detail"))
    return resp.json()
