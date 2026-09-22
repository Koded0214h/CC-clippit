from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
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
        slug=profile.slug,
        public_profile=profile.public_profile,
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
    if "slug" in changes and changes["slug"] is not None and changes["slug"] != profile.slug:
        from modules.creators.models import CreatorProfile

        taken = await db.scalar(select(models.OrganisationProfile.user_id).where(models.OrganisationProfile.slug == changes["slug"])) or \
            await db.scalar(select(CreatorProfile.user_id).where(CreatorProfile.handle == changes["slug"]))
        if taken:
            raise HTTPException(status.HTTP_409_CONFLICT, "That slug is already taken.")
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


# --- onboarding draft lifecycle (GET/PATCH/complete/reset) ---------------------
# The PUT above remains a backwards-compatible one-shot completion call.


def _draft_out(user: User, profile: models.OrganisationProfile) -> schemas.OnboardingDraftOut:
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
    _require_organisation(user)
    return _draft_out(user, await get_or_create_profile(user, db))


@router.patch("/me/onboarding", response_model=schemas.OnboardingDraftOut)
async def autosave_onboarding_draft(
    payload: schemas.OnboardingDraftPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_organisation(user)
    profile = await get_or_create_profile(user, db)
    if payload.revision != profile.draft_revision:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This draft moved on since you last read it (at revision {profile.draft_revision}). Reload and reapply your change.",
        )
    if payload.photo_upload_id is not None:
        await owned_upload(db, payload.photo_upload_id, user.id, kinds=("image",))

    changes = payload.model_dump(mode="json", exclude_unset=True, exclude={"revision", "step"})
    answers = dict(profile.draft_answers or {})
    answers.update({k: v for k, v in changes.items() if v is not None})
    profile.draft_answers = answers
    if payload.step is not None:
        profile.draft_step = payload.step
    profile.draft_revision += 1
    await db.commit()
    await db.refresh(profile)
    return _draft_out(user, profile)


@router.post("/me/onboarding/complete", response_model=schemas.OrganisationProfileOut)
async def complete_onboarding_draft(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Idempotent after completion: calling it again just returns the
    current profile without re-validating or re-copying a stale draft."""
    _require_organisation(user)
    profile = await get_or_create_profile(user, db)
    if user.onboarding_completed:
        return await _out(profile, db)
    try:
        payload = schemas.OrganisationOnboarding.model_validate(profile.draft_answers or {})
    except Exception as exc:  # pydantic ValidationError
        raise HTTPException(422, str(exc)) from exc

    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    profile.draft_answers = None
    profile.draft_step = None
    user.onboarded_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)
    return await _out(profile, db)


@router.delete("/me/onboarding/draft", status_code=status.HTTP_204_NO_CONTENT)
async def reset_onboarding_draft(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _require_organisation(user)
    if user.onboarding_completed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Onboarding is already complete; there's no draft to reset.")
    profile = await get_or_create_profile(user, db)
    profile.draft_answers = None
    profile.draft_step = None
    profile.draft_revision += 1
    await db.commit()
