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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import TTLCache
from core.deps import get_db, require_internal_secret

from . import models, schemas

router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(require_internal_secret)])

# Other modules hit /internal/users/{id} on nearly every request they handle
# (resolving "who is this" for a campaign or submission) — a user's role
# barely ever changes, so a short TTL trades a little staleness for a lot
# fewer DB round trips under load.
_user_cache: TTLCache[uuid.UUID, schemas.InternalUserOut] = TTLCache(ttl_seconds=30, max_size=5000)


@router.get("/users/{user_id}", response_model=schemas.InternalUserOut)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    cached = _user_cache.get(user_id)
    if cached:
        return cached

    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    result = schemas.InternalUserOut.model_validate(user)
    _user_cache.set(user_id, result)
    return result


@router.get("/social-accounts/{user_id}/{platform}/token", response_model=schemas.InternalTokenOut)
async def get_social_token(user_id: uuid.UUID, platform: models.Platform, db: AsyncSession = Depends(get_db)):
    # Not cached: a token is exactly what must never be served stale after
    # a reconnect, and this endpoint isn't called anywhere near as often as
    # the user lookup above.
    account = await db.scalar(
        select(models.SocialAccount).where(
            models.SocialAccount.user_id == user_id, models.SocialAccount.platform == platform
        )
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
