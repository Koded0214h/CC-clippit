import uuid
from datetime import datetime, timezone

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from modules.auth.deps import get_current_user
from core.money import ZERO
from core.platforms import Platform as CorePlatform
from modules.auth.models import Role, SocialAccount, User
from modules.auth.providers import REGISTRY as OAUTH_PROVIDERS
from modules.campaigns import models as campaign_models
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
        bio=profile.bio,
        photo_url=await url_for_upload(db, profile.photo_upload_id),
        interests=list(profile.interests or []),
        platforms=list(profile.intended_platforms or []),
        discovery_source=profile.discovery_source,
        experience=profile.experience,
        goals=list(profile.goals or []),
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
    if user.onboarded_at is None:
        user.onboarded_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)
    return await _profile_out(user, profile, db)


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


@router.get("/me/accounts", response_model=list[schemas.ConnectedAccountOut])
async def my_accounts(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """"Connected accounts": every platform Clippit knows, whether this
    creator has connected it, and when Clippit last read their views there."""
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
        out.append(
            schemas.ConnectedAccountOut(
                platform=platform,
                connectable=platform.value in OAUTH_PROVIDERS,
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

    return (selectinload(campaign_models.Campaign.payout_rule), selectinload(campaign_models.Campaign.rules))
