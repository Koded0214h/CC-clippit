"""The brand's review queue: clips that need a person's decision.

Approving or asking for a correction goes through `submissions.service`
(the same code an automated verifier's outcome would use), so the audit
trail, the notification and the state rules are identical whoever decides.
"""

import uuid
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from core.internal_client import get_internal_client
from modules.auth.deps import get_current_user
from modules.auth.models import Role, SocialAccount, User
from modules.campaigns import service as campaign_service
from modules.campaigns.models import Campaign
from modules.creators.models import CreatorProfile
from modules.submissions import service as submission_service
from modules.submissions.models import Submission, SubmissionStatus, VerificationStatus

from . import schemas

router = APIRouter(prefix="/brand/reviews", tags=["reviews"])

TABS = {
    "needs_review": lambda: (Submission.verification_status == VerificationStatus.needs_review),
    "appeals": lambda: (Submission.verification_status == VerificationStatus.appealed),
    # Decided by a person. Clips an automated check approved never had a
    # human decision to look back on.
    "resolved": lambda: (
        Submission.verification_status.in_((VerificationStatus.approved, VerificationStatus.rejected))
        & Submission.verdict_by.is_not(None)
    ),
}


def _require_reviewer(user: User) -> None:
    if user.role not in (Role.organisation, Role.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a brand or an admin can review submissions")


def _scope(query, user: User):
    """A brand reviews only its own campaigns' clips; admin reviews all."""
    query = query.join(Campaign, Campaign.id == Submission.campaign_id).where(
        Submission.status == SubmissionStatus.submitted
    )
    if user.role == Role.organisation:
        query = query.where(Campaign.event_manager_id == user.id)
    return query


async def _cards(db: AsyncSession, subs: list[Submission]) -> dict[uuid.UUID, schemas.ReviewCard]:
    shaped = {s.id: s for s in await submission_service.shape(db, subs)}
    creator_ids = {s.creator_id for s in subs}
    profiles = {p.user_id: p for p in await db.scalars(select(CreatorProfile).where(CreatorProfile.user_id.in_(creator_ids)))}
    users = {u.id: u for u in await db.scalars(select(User).where(User.id.in_(creator_ids)))}
    handles: dict[tuple[uuid.UUID, str], str | None] = {}
    for acct in await db.scalars(select(SocialAccount).where(SocialAccount.user_id.in_(creator_ids))):
        handles[(acct.user_id, acct.platform.value)] = acct.handle

    out = {}
    for s in subs:
        view = shaped[s.id]
        profile, user = profiles.get(s.creator_id), users.get(s.creator_id)
        out[s.id] = schemas.ReviewCard(
            id=s.id,
            creator_name=profile.display_name if profile else (user.full_name if user else "Creator"),
            creator_handle=handles.get((s.creator_id, s.platform)),
            title=s.title,
            platform=s.platform,
            campaign_slug=view.campaign.slug if view.campaign else "",
            campaign_title=view.campaign.title if view.campaign else "",
            video_url=view.video_url,
            url=s.url,
            confidence=s.verification_confidence,
            issue=s.verification_summary,
            status=s.verification_status,
            is_appeal=s.verification_status == VerificationStatus.appealed,
            submitted_at=s.created_at,
        )
    return out


@router.get("", response_model=schemas.ReviewQueue)
async def review_queue(
    tab: Literal["needs_review", "appeals", "resolved"] = "needs_review",
    campaign_id: uuid.UUID | None = None,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_reviewer(user)

    counts = {}
    for name, predicate in TABS.items():
        query = _scope(select(func.count()).select_from(Submission), user).where(predicate())
        if campaign_id:
            query = query.where(Submission.campaign_id == campaign_id)
        counts[name] = int(await db.scalar(query) or 0)

    query = _scope(select(Submission), user).where(TABS[tab]())
    if campaign_id:
        query = query.where(Submission.campaign_id == campaign_id)
    # Oldest first: the queue is worked through in the order clips arrived.
    order = Submission.verdict_at.desc() if tab == "resolved" else Submission.created_at.asc()
    subs = list(await db.scalars(query.order_by(order).limit(limit).offset(offset)))
    cards = await _cards(db, subs)
    return schemas.ReviewQueue(
        tab=tab, counts=schemas.ReviewCounts(**counts), items=[cards[s.id] for s in subs]
    )


async def _load(db: AsyncSession, submission_id: uuid.UUID, user: User) -> tuple[Submission, Campaign]:
    submission = await db.scalar(_scope(select(Submission), user).where(Submission.id == submission_id))
    if submission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    campaign = await campaign_service.resolve(db, str(submission.campaign_id))
    return submission, campaign


@router.get("/{submission_id}", response_model=schemas.ReviewDetail)
async def review_detail(submission_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _require_reviewer(user)
    submission, _ = await _load(db, submission_id, user)
    card = (await _cards(db, [submission]))[submission.id]
    view = (await submission_service.shape(db, [submission]))[0]
    v = view.verification
    flagged = next((r for r in v.requirements if r.verdict.value == "review"), None) or v.failed_requirement
    return schemas.ReviewDetail(
        **card.model_dump(),
        creator_id=submission.creator_id,
        requirements=v.requirements,
        passed=v.passed,
        total=v.total,
        flagged_requirement=flagged,
        appeal=v.appeal,
        decided_at=v.verdict_at,
        decided_by_human=v.decided_by_human,
    )


@router.post("/{submission_id}/approve", response_model=schemas.ReviewDetail)
async def approve(
    submission_id: uuid.UUID,
    payload: schemas.ApproveRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_internal_client),
):
    """Approve the clip (or, on an appeal, overturn the rejection). From this
    moment its views can earn."""
    _require_reviewer(user)
    submission, campaign = await _load(db, submission_id, user)
    try:
        await submission_service.approve(db, submission, campaign, user, note=payload.note if payload else None)
    except submission_service.TransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, exc.message) from exc
    await db.commit()

    # Book what the clip has already earned, so the creator sees it straight
    # away rather than at the next scheduled settlement. Best effort: the
    # scheduled job would catch it anyway.
    from modules.earnings import service as earnings_service

    try:
        await earnings_service.settle_submission(db, submission.id, client)
        await db.commit()
    except earnings_service.IntelligenceUnavailable:
        await db.rollback()
    return await review_detail(submission_id, user, db)


@router.post("/{submission_id}/request-correction", response_model=schemas.ReviewDetail)
async def request_correction(
    submission_id: uuid.UUID,
    payload: schemas.CorrectionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject with the failed requirement and a reason the creator will read.
    They can appeal it, or submit a corrected post."""
    _require_reviewer(user)
    submission, campaign = await _load(db, submission_id, user)
    try:
        await submission_service.request_correction(
            db, submission, campaign, user, reason=payload.reason, requirement_id=payload.requirement_id
        )
    except submission_service.TransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, exc.message) from exc
    await db.commit()
    return await review_detail(submission_id, user, db)
