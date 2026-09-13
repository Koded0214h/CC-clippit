"""Endpoints meant for other modules to call, not the browser.

Guarded by a shared secret (X-Internal-Secret, see core.deps.require_internal_secret)
instead of a user's JWT — kept even inside a single monolith so this boundary
stays honest if Campaign Management, Content Submission, Intelligence Engine
or Payout Service ever get split into their own deployable later. Used by:
  - Campaign Management / Content Submission (Adam): resolve a user's role
  - Intelligence Engine (Koded): read a creator's platform access token
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.deps import get_db, require_internal_secret

from . import models, schemas

router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(require_internal_secret)])


@router.get("/users/{user_id}", response_model=schemas.InternalUserOut)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return schemas.InternalUserOut.model_validate(user)


@router.get("/social-accounts/{user_id}/{platform}/token", response_model=schemas.InternalTokenOut)
def get_social_token(user_id: uuid.UUID, platform: models.Platform, db: Session = Depends(get_db)):
    account = (
        db.query(models.SocialAccount)
        .filter(models.SocialAccount.user_id == user_id, models.SocialAccount.platform == platform)
        .first()
    )
    if not account:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No connected account for this platform")
    if account.expires_at and account.expires_at < datetime.now(timezone.utc):
        # TikTok's token can be refreshed with account.refresh_token; the other
        # three providers don't expose a refresh flow in the ported prototypes
        # yet — the caller gets a 409 rather than a silently stale token.
        raise HTTPException(status.HTTP_409_CONFLICT, "Token expired; re-connect this account")
    return schemas.InternalTokenOut(
        access_token=account.access_token,
        platform_user_id=account.platform_user_id,
        expires_at=account.expires_at,
    )
