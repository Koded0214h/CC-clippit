"""The profile is where a signed-in user manages their account — including
connecting social platforms. Connecting a social account is a profile
action taken after a normal email/password signup, never itself a signup
or login mechanism: there is no "sign up with TikTok". The frontend's
profile page reads this router's GET /profile once and renders the
"Connect TikTok / Facebook / Instagram / Threads" buttons from
`social_accounts`, pointing at /social/{platform}/login (see social_router.py)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db

from . import models, schemas
from .deps import get_current_user

router = APIRouter(prefix="/profile", tags=["profile"])


async def _get_or_create_preferences(user: models.User, db: AsyncSession) -> models.UserPreferences:
    prefs = await db.get(models.UserPreferences, user.id)
    if not prefs:
        # Safety net for users created before this table existed; normally
        # /auth/signup creates this row up front.
        prefs = models.UserPreferences(user_id=user.id)
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)
    return prefs


@router.get("", response_model=schemas.ProfileOut)
async def get_profile(user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    accounts = await db.scalars(select(models.SocialAccount).where(models.SocialAccount.user_id == user.id))
    prefs = await _get_or_create_preferences(user, db)
    return schemas.ProfileOut(
        user=schemas.UserOut.model_validate(user),
        social_accounts=[schemas.SocialAccountOut.from_model(a) for a in accounts],
        preferences=schemas.PreferencesOut.model_validate(prefs),
    )


@router.get("/preferences", response_model=schemas.PreferencesOut)
async def get_preferences(user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    prefs = await _get_or_create_preferences(user, db)
    return schemas.PreferencesOut.model_validate(prefs)


@router.patch("/preferences", response_model=schemas.PreferencesOut)
async def update_preferences(
    payload: schemas.PreferencesUpdate,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await _get_or_create_preferences(user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(prefs, field, value)
    await db.commit()
    await db.refresh(prefs)
    return schemas.PreferencesOut.model_validate(prefs)
