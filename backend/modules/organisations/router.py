from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from modules.auth.deps import get_current_user
from modules.auth.models import Role, User
from modules.uploads.router import owned_upload
from modules.uploads.service import url_for_upload

from . import models, schemas

router = APIRouter(prefix="/organisations", tags=["organisations"])


def _require_organisation(user: User) -> None:
    if user.role != Role.organisation:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an organisation account has this")


async def _out(profile: models.OrganisationProfile, db: AsyncSession) -> schemas.OrganisationProfileOut:
    return schemas.OrganisationProfileOut(
        user_id=profile.user_id,
        name=profile.name,
        bio=profile.bio,
        website=profile.website,
        photo_url=await url_for_upload(db, profile.photo_upload_id),
        finance_email=profile.finance_email,
        business_legal_name=profile.business_legal_name,
        business_verified=profile.business_verified,
        production_workflow=profile.production_workflow,
        team_size=profile.team_size,
        campaign_goal=profile.campaign_goal,
        budget_range=profile.budget_range,
        updated_at=profile.updated_at,
    )


async def get_or_create_profile(user: User, db: AsyncSession) -> models.OrganisationProfile:
    """Every organisation has a profile from its first request onward — the
    name defaults to the signup name so no screen has to handle "none yet"."""
    profile = await db.get(models.OrganisationProfile, user.id)
    if profile is None:
        profile = models.OrganisationProfile(user_id=user.id, name=user.full_name[:80], finance_email=user.email)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


@router.get("/me/profile", response_model=schemas.OrganisationProfileOut)
async def get_profile(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _require_organisation(user)
    return await _out(await get_or_create_profile(user, db), db)


@router.put("/me/profile", response_model=schemas.OrganisationProfileOut)
async def update_profile(
    payload: schemas.OrganisationProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_organisation(user)
    profile = await get_or_create_profile(user, db)
    changes = payload.model_dump(exclude_unset=True)
    if "photo_upload_id" in changes and changes["photo_upload_id"] is not None:
        await owned_upload(db, changes["photo_upload_id"], user.id, kinds=("image",))
    for field, value in changes.items():
        if field == "finance_email" and value is not None:
            value = str(value)
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return await _out(profile, db)


@router.put("/me/onboarding", response_model=schemas.OrganisationProfileOut)
async def complete_onboarding(
    payload: schemas.OrganisationOnboarding,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Saves the onboarding answers and marks onboarding done. Safe to call
    again: it just overwrites the answers."""
    _require_organisation(user)
    profile = await get_or_create_profile(user, db)
    if payload.photo_upload_id is not None:
        await owned_upload(db, payload.photo_upload_id, user.id, kinds=("image",))
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    if user.onboarded_at is None:
        user.onboarded_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)
    return await _out(profile, db)
