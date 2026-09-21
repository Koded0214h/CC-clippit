import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from modules.auth.deps import get_current_user
from modules.auth.models import Role, User
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
