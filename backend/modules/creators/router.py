import uuid
from datetime import datetime, timezone

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.deps import get_db
from modules.auth.deps import get_current_user
from core.money import ZERO
from core.platforms import V1_PLATFORMS, Platform as CorePlatform
from modules.auth import schemas as auth_schemas
from modules.auth.models import Role, SocialAccount, User
from modules.auth.providers import is_connectable
from modules.campaigns import models as campaign_models
from modules.campaigns import schemas as campaign_schemas
from modules.campaigns import service as campaign_service
from modules.earnings import queries as earnings_queries
from modules.earnings.models import EarningAccount
from modules.submissions.models import Submission, SubmissionStatus, VerificationStatus
from modules.uploads.router import owned_upload
from modules.uploads.service import url_for_upload

from . import models, schemas

router = APIRouter(prefix="/creators", tags=["creators"])


@router.put("/me/bank-details", response_model=schemas.BankAccountOut)
async def set_bank_details(
    payload: schemas.BankAccountIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != Role.creator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a creator account has bank details")

    account = await db.get(models.CreatorBankAccount, user.id)
    if account:
        # Changing where money goes always re-requires verification — see
        # the model docstring. Setting the same details again also resets
        # it, deliberately: there's no way to tell "resubmitted unchanged"
        # from "changed back" from here, so the safer one always wins.
        account.bank_code = payload.bank_code
        account.bank_name = payload.bank_name
        account.account_number = payload.account_number
        account.account_name = None
        account.verified = False
        account.verified_at = None
    else:
        account = models.CreatorBankAccount(creator_id=user.id, **payload.model_dump())
        db.add(account)

    await db.commit()
    await db.refresh(account)
    return schemas.BankAccountOut.from_model(account)


@router.delete("/me/bank-details", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bank_details(
    payload: auth_schemas.StepUpOnly,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Removes the saved destination. A masked snapshot survives on any
    existing payout receipt (those store their own copy at send time —
    see `Payout.bank_code`/`account_number`, never a live join to this
    table), so deleting it here never breaks past provenance."""
    from modules.auth.router import consume_step_up

    if user.role != Role.creator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a creator account has bank details")
    account = await db.get(models.CreatorBankAccount, user.id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bank details on file yet")

    from modules.payouts.models import Payout, PayoutStatus

    pending = await db.scalar(
        select(Payout.id).where(
            Payout.creator_id == user.id, Payout.status.in_((PayoutStatus.pending, PayoutStatus.processing))
        )
    )
    if pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "A payout is still in flight — wait for it to finish first.")

    await consume_step_up(db, payload.step_up_token, "delete_bank_details", user.id)
    await db.delete(account)
    await db.commit()


@router.get("/me/bank-details", response_model=schemas.BankAccountOut)
async def get_my_bank_details(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != Role.creator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a creator account has bank details")

    account = await db.get(models.CreatorBankAccount, user.id)
    if not account:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bank details on file yet")
    return schemas.BankAccountOut.from_model(account)


@router.get("/{creator_id}/bank-details", response_model=schemas.BankAccountOut)
async def get_bank_details_for_admin(
    creator_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Support/dispute access only — an event manager has no business case
    to see a creator's bank details, so this is admin-only rather than
    following campaigns'/submissions' owner-or-admin pattern."""
    if user.role != Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")

    account = await db.get(models.CreatorBankAccount, creator_id)
    if not account:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bank details on file for this creator")
    return schemas.BankAccountOut.from_model(account)


# --- Profile & onboarding ---------------------------------------------------


def _require_creator(user: User) -> None:
    if user.role != Role.creator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a creator account has this")


async def _profile_out(user: User, profile: models.CreatorProfile, db: AsyncSession) -> schemas.CreatorProfileOut:
    return schemas.CreatorProfileOut(
        user_id=profile.user_id,
        display_name=profile.display_name,
        handle=profile.handle,
        public_profile=profile.public_profile,
        bio=profile.bio,
        photo_url=await url_for_upload(db, profile.photo_upload_id),
        interests=list(profile.interests or []),
        platforms=list(profile.intended_platforms or []),
        discovery_source=profile.discovery_source,
        experience=profile.experience,
        goals=list(profile.goals or []),
        country=profile.country,
        location=profile.location,
        viewing_interests=list(profile.viewing_interests or []),
        onboarding_completed=user.onboarding_completed,
        updated_at=profile.updated_at,
    )


async def get_or_create_profile(user: User, db: AsyncSession) -> models.CreatorProfile:
    profile = await db.get(models.CreatorProfile, user.id)
    if profile is None:
        profile = models.CreatorProfile(user_id=user.id, display_name=user.full_name[:80])
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


@router.get("/me/profile", response_model=schemas.CreatorProfileOut)
async def get_my_profile(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _require_creator(user)
    return await _profile_out(user, await get_or_create_profile(user, db), db)


@router.put("/me/profile", response_model=schemas.CreatorProfileOut)
async def update_my_profile(
    payload: schemas.CreatorProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_creator(user)
    profile = await get_or_create_profile(user, db)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("photo_upload_id") is not None:
        await owned_upload(db, changes["photo_upload_id"], user.id, kinds=("image",))
    if "handle" in changes and changes["handle"] is not None and changes["handle"] != profile.handle:
        from modules.organisations.models import OrganisationProfile

        taken = await db.scalar(select(models.CreatorProfile.user_id).where(models.CreatorProfile.handle == changes["handle"])) or \
            await db.scalar(select(OrganisationProfile.user_id).where(OrganisationProfile.slug == changes["handle"]))
        if taken:
            raise HTTPException(status.HTTP_409_CONFLICT, "That handle is already taken.")
    for field, value in changes.items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return await _profile_out(user, profile, db)


@router.put("/me/onboarding", response_model=schemas.CreatorProfileOut)
async def complete_onboarding(
    payload: schemas.CreatorOnboarding,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Saves the onboarding answers and marks onboarding done. Idempotent —
    calling it again overwrites the answers."""
    _require_creator(user)
    profile = await get_or_create_profile(user, db)
    if payload.photo_upload_id is not None:
        await owned_upload(db, payload.photo_upload_id, user.id, kinds=("image",))
        profile.photo_upload_id = payload.photo_upload_id
    profile.display_name = payload.display_name
    profile.interests = payload.interests
    profile.intended_platforms = [p.value for p in payload.platforms]
    profile.discovery_source = payload.discovery_source
    profile.experience = payload.experience
    profile.goals = payload.goals
    profile.country = payload.country
    profile.location = payload.location
    profile.viewing_interests = payload.viewing_interests
    profile.draft_answers = None
    profile.draft_step = None
    if user.onboarded_at is None:
        user.onboarded_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)
    return await _profile_out(user, profile, db)


# --- onboarding draft lifecycle (GET/PATCH/complete/reset) ---------------------
#
# The PUT above remains a backwards-compatible one-shot completion call.
# This is the resumable version: autosave after every screen so a phone
# refresh or a dropped connection never loses progress.


def _draft_out(user: User, profile: models.CreatorProfile) -> schemas.OnboardingDraftOut:
    status_ = "completed" if user.onboarding_completed else ("in_progress" if profile.draft_answers else "not_started")
    return schemas.OnboardingDraftOut(
        status=status_,
        step=profile.draft_step,
        revision=profile.draft_revision,
        answers=profile.draft_answers or {},
        completed_at=user.onboarded_at,
        updated_at=profile.updated_at,
    )


@router.get("/me/onboarding", response_model=schemas.OnboardingDraftOut)
async def get_onboarding_draft(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _require_creator(user)
    return _draft_out(user, await get_or_create_profile(user, db))


@router.patch("/me/onboarding", response_model=schemas.OnboardingDraftOut)
async def autosave_onboarding_draft(
    payload: schemas.OnboardingDraftPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_creator(user)
    profile = await get_or_create_profile(user, db)
    if payload.revision != profile.draft_revision:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This draft moved on since you last read it (at revision {profile.draft_revision}). Reload and reapply your change.",
        )
    if payload.photo_upload_id is not None:
        await owned_upload(db, payload.photo_upload_id, user.id, kinds=("image",))

    changes = payload.model_dump(mode="json", exclude_unset=True, exclude={"revision", "step"})
    if "platforms" in changes and changes["platforms"] is not None:
        changes["platforms"] = [p.value if hasattr(p, "value") else p for p in changes["platforms"]]
    answers = dict(profile.draft_answers or {})
    answers.update({k: v for k, v in changes.items() if v is not None})
    profile.draft_answers = answers
    if payload.step is not None:
        profile.draft_step = payload.step
    profile.draft_revision += 1
    await db.commit()
    await db.refresh(profile)
    return _draft_out(user, profile)


@router.post("/me/onboarding/complete", response_model=schemas.CreatorProfileOut)
async def complete_onboarding_draft(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Validates the accumulated draft as a whole and, only if it's
    complete, atomically copies it into the real profile. Calling this
    again once onboarding is done just returns the current profile —
    it never re-validates or re-copies a stale draft over it."""
    _require_creator(user)
    profile = await get_or_create_profile(user, db)
    if user.onboarding_completed:
        return await _profile_out(user, profile, db)
    try:
        payload = schemas.CreatorOnboarding.model_validate(profile.draft_answers or {})
    except Exception as exc:  # pydantic ValidationError
        raise HTTPException(422, str(exc)) from exc

    profile.display_name = payload.display_name
    profile.interests = payload.interests
    profile.intended_platforms = [p.value for p in payload.platforms]
    profile.photo_upload_id = payload.photo_upload_id
    profile.discovery_source = payload.discovery_source
    profile.experience = payload.experience
    profile.goals = payload.goals
    profile.country = payload.country
    profile.location = payload.location
    profile.viewing_interests = payload.viewing_interests
    profile.draft_answers = None
    profile.draft_step = None
    user.onboarded_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)
    return await _profile_out(user, profile, db)


@router.delete("/me/onboarding/draft", status_code=status.HTTP_204_NO_CONTENT)
async def reset_onboarding_draft(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Resets an incomplete draft. Never touches the account, a completed
    onboarding record, the profile, or any already-uploaded photo."""
    _require_creator(user)
    if user.onboarding_completed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Onboarding is already complete; there's no draft to reset.")
    profile = await get_or_create_profile(user, db)
    profile.draft_answers = None
    profile.draft_step = None
    profile.draft_revision += 1
    await db.commit()


# --- clips, connected accounts, home ------------------------------------------------


_CLIP_STATES = {
    "approved": ("Approved", "/dashboard/submissions/approved"),
    "checking": ("Checking", "/dashboard/submissions/processing"),
    "needs_attention": ("Needs attention", "/dashboard/submissions/rejected"),
    "appealed": ("Appeal in review", "/dashboard/submissions/appeal"),
    "withdrawn": ("Withdrawn", "/dashboard/clips"),
}


def _clip_state(sub: Submission) -> str:
    if sub.status == SubmissionStatus.withdrawn:
        return "withdrawn"
    if sub.status == SubmissionStatus.rejected or sub.verification_status == VerificationStatus.rejected:
        return "needs_attention"
    if sub.verification_status == VerificationStatus.approved:
        return "approved"
    if sub.verification_status == VerificationStatus.appealed:
        return "appealed"
    return "checking"


@router.get("/me/clips", response_model=schemas.ClipsOut)
async def my_clips(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """"My clips": every submission with its status, verified views and what
    it has earned, plus the three headline totals."""
    _require_creator(user)
    rows = (
        await db.execute(
            select(Submission, campaign_models.Campaign, EarningAccount)
            .join(campaign_models.Campaign, campaign_models.Campaign.id == Submission.campaign_id)
            .outerjoin(EarningAccount, EarningAccount.submission_id == Submission.id)
            .where(Submission.creator_id == user.id)
            .order_by(Submission.created_at.desc())
        )
    ).all()
    brand_map = await campaign_service.brands(db, {c.event_manager_id for _, c, _ in rows})

    items, active, views, earned = [], 0, 0, ZERO
    for sub, campaign, account in rows:
        state = _clip_state(sub)
        label, link = _CLIP_STATES[state]
        clip_views = int(account.cumulative_views) if account else 0
        clip_earned = account.accrued_amount if account else ZERO
        if state in ("approved", "checking", "appealed"):
            active += 1
        views += clip_views
        earned += clip_earned
        items.append(
            schemas.ClipRow(
                id=sub.id, title=sub.title, platform=sub.platform, campaign_slug=campaign.slug,
                campaign_title=campaign.title,
                brand=brand_map[campaign.event_manager_id].name if campaign.event_manager_id in brand_map else None,
                status=state, label=label, verified_views=clip_views, earned=clip_earned,
                link=f"{link}?id={sub.id}", submitted_at=sub.created_at,
            )
        )
    return schemas.ClipsOut(active_clips=active, verified_views=views, total_earned=earned, items=items)


@router.get("/me/campaigns", response_model=list[campaign_schemas.MyCampaignRow])
async def my_campaigns(
    membership_status: str | None = Query(None, description="joined | submitted | active | completed | left"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Every campaign this creator has a relationship with — joined,
    submitted to, or left — distinct from the public feed's Joined filter,
    which only lists open ones."""
    _require_creator(user)
    memberships = {
        m.campaign_id: m
        for m in await db.scalars(select(campaign_models.CampaignMembership).where(campaign_models.CampaignMembership.creator_id == user.id))
    }
    submissions = {
        s.campaign_id: s
        for s in await db.scalars(
            select(Submission)
            .where(Submission.creator_id == user.id, Submission.status != SubmissionStatus.withdrawn)
            .order_by(Submission.created_at.desc())
        )
    }
    campaign_ids = set(memberships) | set(submissions)
    if not campaign_ids:
        return []

    campaigns = {
        c.id: c
        for c in await db.scalars(
            select(campaign_models.Campaign)
            .where(campaign_models.Campaign.id.in_(campaign_ids))
            .options(
                selectinload(campaign_models.Campaign.payout_rule),
                selectinload(campaign_models.Campaign.rules),
                selectinload(campaign_models.Campaign.performance_metrics),
            )
            .order_by(campaign_models.Campaign.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    }
    if not campaigns:
        return []
    outs = {
        c.id: out for c, out in zip(campaigns.values(), await campaign_service.build_outs(db, list(campaigns.values()), user))
    }

    rows = []
    for campaign_id, campaign in campaigns.items():
        membership = memberships.get(campaign_id)
        submission = submissions.get(campaign_id)
        if campaign.status == campaign_models.CampaignStatus.closed:
            state = "completed"
        elif submission and submission.verification_status == VerificationStatus.approved:
            state = "active"
        elif submission:
            state = "submitted"
        elif membership and membership.left_at is not None:
            state = "left"
        else:
            state = "joined"
        if membership_status and state != membership_status:
            continue
        rows.append(
            campaign_schemas.MyCampaignRow(
                campaign=outs[campaign_id],
                membership_status=state,
                joined_at=membership.joined_at if membership else submission.created_at if submission else None,
                left_at=membership.left_at if membership else None,
                submission_id=submission.id if submission else None,
                submission_status=submission.verification_status.value if submission else None,
            )
        )
    return rows


@router.get("/me/accounts", response_model=list[schemas.ConnectedAccountOut])
async def my_accounts(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """"Connected accounts": every V1 platform (plus any other one this
    creator already connected, so they can disconnect it), whether it's
    connected, and when Clippit last read their views there."""
    _require_creator(user)
    connected = {a.platform.value: a for a in await db.scalars(select(SocialAccount).where(SocialAccount.user_id == user.id))}
    last_read = {
        platform: at
        for platform, at in await db.execute(
            select(Submission.platform, func.max(EarningAccount.last_settled_at))
            .join(EarningAccount, EarningAccount.submission_id == Submission.id)
            .where(Submission.creator_id == user.id)
            .group_by(Submission.platform)
        )
    }
    out = []
    for platform in CorePlatform:
        account = connected.get(platform.value)
        if platform not in V1_PLATFORMS and account is None:
            continue
        out.append(
            schemas.ConnectedAccountOut(
                platform=platform,
                connectable=is_connectable(platform.value),
                connected=account is not None,
                handle=account.handle if account else None,
                display_name=account.display_name if account else None,
                connected_at=account.created_at if account else None,
                last_checked_at=last_read.get(platform.value),
            )
        )
    return out


@router.get("/me/overview", response_model=schemas.CreatorOverview)
async def my_overview(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """The dashboard home: the campaign closing soonest, how many new ones
    match this creator's lanes, and the money card."""
    _require_creator(user)
    at = campaign_service.now()
    live = (
        select(campaign_models.Campaign)
        .where(
            campaign_models.Campaign.status == campaign_models.CampaignStatus.active,
            campaign_models.Campaign.ends_at > at,
        )
    )
    closing = await db.scalar(
        live.options(*campaign_service_options()).order_by(campaign_models.Campaign.ends_at.asc()).limit(1)
    )
    closing_out = (await campaign_service.build_outs(db, [closing], user))[0] if closing else None

    profile = await db.get(models.CreatorProfile, user.id)
    lanes = [i.lower() for i in (profile.interests if profile else [])]
    matches = 0
    if lanes:
        joined = select(Submission.campaign_id).where(Submission.creator_id == user.id, Submission.status != SubmissionStatus.withdrawn)
        matches = await db.scalar(
            select(func.count()).select_from(campaign_models.Campaign).where(
                campaign_models.Campaign.status == campaign_models.CampaignStatus.active,
                campaign_models.Campaign.created_at >= at - timedelta(days=7),
                func.lower(campaign_models.Campaign.category).in_(lanes),
                campaign_models.Campaign.id.not_in(joined),
            )
        )
    return schemas.CreatorOverview(
        closing_soon=closing_out, new_matches=int(matches or 0), earnings=await earnings_queries.summary(db, user.id)
    )


def campaign_service_options():
    from sqlalchemy.orm import selectinload

    return (
        selectinload(campaign_models.Campaign.payout_rule),
        selectinload(campaign_models.Campaign.rules),
        selectinload(campaign_models.Campaign.performance_metrics),
    )
