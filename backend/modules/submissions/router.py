"""Creator submits a link against a live campaign. This module owns the
submission's own lifecycle and its brief verdict — performance and trust are
never copied onto it, they're read live from Intelligence's internal API every
time, via `core.internal_client` (an in-process ASGI call that exercises the
real `/internal/*` contract, X-Internal-Secret included, so nothing here
changes the day that module becomes a separate deployable).
"""

import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from core.internal_client import get_internal_client
from core.money import ZERO, to_decimal
from modules.audit import service as audit
from modules.auth.deps import get_current_user, get_verified_user
from modules.auth.models import Platform as AuthPlatform
from modules.auth.models import Role, SocialAccount, User
from modules.campaigns import service as campaign_service
from modules.campaigns.models import AttributionLink, Campaign, CampaignStatus, PerformanceEvent
from modules.earnings.models import EarningAccount, EarningEntry
from modules.intelligence.contracts import PerformanceResult, SubmissionRef
from modules.uploads.router import owned_upload

from . import models, schemas, service

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


async def _one(db: AsyncSession, submission: models.Submission) -> schemas.SubmissionOut:
    return (await service.shape(db, [submission]))[0]


async def _register(
    db: AsyncSession,
    client: httpx.AsyncClient,
    user: User,
    campaign: Campaign,
    *,
    platform,
    url: str,
    title: str | None,
    video_upload_id: uuid.UUID | None,
    resubmitted_from_id: uuid.UUID | None = None,
) -> models.Submission:
    """Everything `POST /submissions` and `POST /submissions/{id}/resubmit`
    share: campaign/account checks, registering with Intelligence, and
    running the brief verifier. The caller has already validated whatever
    is specific to it (predecessor eligibility, for a resubmission)."""
    if campaign.status != CampaignStatus.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found or not accepting submissions")
    if not campaign_service.is_open_for_entries(campaign):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "campaign_not_accepting", "message": "This campaign isn't taking new clips right now."},
        )
    if platform.value not in campaign.platforms:
        raise HTTPException(422, f"This campaign doesn't accept {platform.value} submissions")

    max_submissions = campaign.payout_rule.max_submissions if campaign.payout_rule else None
    if max_submissions is not None and resubmitted_from_id is None:
        existing = await db.scalar(
            select(func.count()).select_from(models.Submission).where(
                models.Submission.campaign_id == campaign.id,
                models.Submission.creator_id == user.id,
                models.Submission.status != models.SubmissionStatus.rejected,
                models.Submission.resubmitted_from_id.is_(None),
            )
        )
        if (existing or 0) >= max_submissions:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"You've reached this campaign's limit of {max_submissions} submission(s).",
            )

    has_account = (
        await db.scalar(
            select(SocialAccount.id).where(
                SocialAccount.user_id == user.id, SocialAccount.platform == AuthPlatform(platform.value)
            )
        )
        is not None
    )
    if not has_account:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Connect your {platform.value} account from your profile before submitting"
        )
    if video_upload_id:
        await owned_upload(db, video_upload_id, user.id, kinds=("video",))

    submission = models.Submission(
        campaign_id=campaign.id,
        creator_id=user.id,
        platform=platform.value,
        url=url,
        title=title,
        video_upload_id=video_upload_id,
        resubmitted_from_id=resubmitted_from_id,
    )
    db.add(submission)
    await db.flush()  # assigns submission.id (client-side default) before we reference it below
    unbound_links = await db.scalars(
        select(AttributionLink).where(
            AttributionLink.campaign_id == campaign.id,
            AttributionLink.creator_id == user.id,
            AttributionLink.submission_id.is_(None),
            AttributionLink.active.is_(True),
        )
    )
    for attribution_link in unbound_links:
        attribution_link.submission_id = submission.id
        unbound_events = await db.scalars(
            select(PerformanceEvent).where(
                PerformanceEvent.attribution_link_id == attribution_link.id,
                PerformanceEvent.submission_id.is_(None),
            )
        )
        for performance_event in unbound_events:
            performance_event.submission_id = submission.id

    ref = SubmissionRef(
        submission_id=submission.id, campaign_id=campaign.id, creator_id=user.id, platform=platform, url=url
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
        submission.verification_status = models.VerificationStatus.rejected
        submission.verification_summary = message
        audit.record(
            db, "submission.link_rejected", actor_id=user.id, submission_id=submission.id,
            campaign_id=campaign.id, code=code,
        )
        await db.commit()
        raise HTTPException(resp.status_code, detail)

    kind = "submission.resubmitted" if resubmitted_from_id else "submission.created"
    audit.record(db, kind, actor_id=user.id, submission_id=submission.id, campaign_id=campaign.id)
    await service.run_verification(db, submission, campaign)
    await db.commit()
    await db.refresh(submission)
    return submission


@router.post("", response_model=schemas.SubmissionOut, status_code=status.HTTP_201_CREATED)
async def create_submission(
    payload: schemas.SubmissionCreate,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_internal_client),
):
    if user.role != Role.creator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a creator account can submit content")

    campaign = await campaign_service.resolve(db, str(payload.campaign_id))
    if not campaign:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found or not accepting submissions")
    submission = await _register(
        db, client, user, campaign,
        platform=payload.platform, url=payload.url, title=payload.title, video_upload_id=payload.video_upload_id,
    )
    return await _one(db, submission)


MAX_RESUBMISSIONS = 3  # the original attempt plus up to two corrections


@router.post("/{submission_id}/resubmit", response_model=schemas.SubmissionOut, status_code=status.HTTP_201_CREATED)
async def resubmit(
    submission_id: uuid.UUID,
    payload: schemas.ResubmitIn,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_internal_client),
):
    """A corrected clip against the same campaign, linked to the verdict it
    corrects. The original submission — its verdict, requirement results,
    and appeal — is untouched; it's superseded, not rewritten."""
    predecessor = await _get_visible_submission(submission_id, user, db)
    if user.role != Role.creator or predecessor.creator_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the creator who submitted this can resubmit it")
    corrigible = predecessor.status == models.SubmissionStatus.rejected or (
        predecessor.status == models.SubmissionStatus.submitted
        and predecessor.verification_status == models.VerificationStatus.rejected
    )
    if not corrigible:
        raise HTTPException(status.HTTP_409_CONFLICT, "This submission isn't in a state that can be corrected.")

    chain_length, node = 1, predecessor
    while node.resubmitted_from_id is not None:
        node = await db.get(models.Submission, node.resubmitted_from_id)
        if node is None:
            break
        chain_length += 1
    if chain_length >= MAX_RESUBMISSIONS:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This clip has already been corrected the maximum number of times."
        )

    campaign = await campaign_service.resolve(db, str(predecessor.campaign_id))
    if not campaign:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found or not accepting submissions")
    submission = await _register(
        db, client, user, campaign,
        platform=payload.platform, url=payload.url, title=payload.title, video_upload_id=payload.video_upload_id,
        resubmitted_from_id=predecessor.id,
    )
    return await _one(db, submission)


@router.get("", response_model=list[schemas.SubmissionOut])
async def list_submissions(
    campaign_id: uuid.UUID | None = None,
    verification: models.VerificationStatus | None = None,
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
    if verification:
        query = query.where(models.Submission.verification_status == verification)
    query = query.order_by(models.Submission.created_at.desc())
    return await service.shape(db, list(await db.scalars(query)))


@router.get("/{submission_id}", response_model=schemas.SubmissionOut)
async def get_submission(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _one(db, await _get_visible_submission(submission_id, user, db))


@router.post("/{submission_id}/withdraw", response_model=schemas.SubmissionOut)
async def withdraw_submission(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_internal_client),
):
    """Withdraw locally and tell Intelligence to stop polling (D17). What the
    clip already earned stays payable; nothing more accrues."""
    submission = await _get_visible_submission(submission_id, user, db)
    if user.role == Role.creator and submission.creator_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your submission")
    if user.role == Role.organisation:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the creator or an admin can withdraw a submission")
    if submission.status != models.SubmissionStatus.submitted:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Submission is already {submission.status.value}")

    submission.status = models.SubmissionStatus.withdrawn
    audit.record(db, "submission.withdrawn", actor_id=user.id, submission_id=submission.id, campaign_id=submission.campaign_id)
    await db.commit()
    try:
        await client.post(f"/internal/submissions/{submission_id}/tracking/stop")
    except httpx.HTTPError:
        # The row is withdrawn either way; the 30-day cap is the backstop
        # if this call misses.
        pass
    return await _one(db, submission)


@router.post("/{submission_id}/appeal", response_model=schemas.SubmissionOut, status_code=status.HTTP_201_CREATED)
async def appeal_verdict(
    submission_id: uuid.UUID,
    payload: schemas.AppealCreate,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """"Request review": the creator explains what the check missed and can
    attach evidence. One appeal per verdict; the original verdict is kept."""
    submission = await _get_visible_submission(submission_id, user, db)
    if user.role != Role.creator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the creator can appeal")
    if payload.evidence_upload_id:
        await owned_upload(db, payload.evidence_upload_id, user.id, kinds=("evidence", "image", "video"))
    campaign = await campaign_service.resolve(db, str(submission.campaign_id))
    try:
        await service.submit_appeal(
            db, submission, campaign, user, reason=payload.reason, evidence_upload_id=payload.evidence_upload_id
        )
    except service.TransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, exc.message) from exc
    await db.commit()
    return await _one(db, submission)


@router.get("/{submission_id}/earnings", response_model=schemas.SubmissionEarningsOut)
async def submission_earnings(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accrued so far, and when the next amount becomes payable."""
    await _get_visible_submission(submission_id, user, db)
    at = campaign_service.now()
    account = await db.get(EarningAccount, submission_id)
    payable_now = to_decimal(
        await db.scalar(
            select(func.coalesce(func.sum(EarningEntry.amount), 0)).where(
                EarningEntry.submission_id == submission_id, EarningEntry.payable_at <= at
            )
        )
    )
    next_payable = await db.scalar(
        select(func.min(EarningEntry.payable_at)).where(
            EarningEntry.submission_id == submission_id, EarningEntry.payable_at > at
        )
    )
    return schemas.SubmissionEarningsOut(
        submission_id=submission_id,
        verified_views=int(account.cumulative_views) if account else 0,
        accrued=to_decimal(account.accrued_amount) if account else ZERO,
        next_payable_at=next_payable,
        payable_now=payable_now,
    )


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
