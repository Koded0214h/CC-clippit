import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.deps import get_db
from core.security import create_oauth_state_token, decode_oauth_state_token

from . import models, schemas
from .deps import get_current_user, get_current_user_allow_query
from .providers import get_provider
from .providers.base import OAuthError

router = APIRouter(prefix="/social", tags=["social"])
settings = get_settings()


@router.get("/accounts", response_model=list[schemas.SocialAccountOut])
async def list_accounts(
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    accounts = await db.scalars(select(models.SocialAccount).where(models.SocialAccount.user_id == user.id))
    return [schemas.SocialAccountOut.from_model(a) for a in accounts]


@router.delete("/{platform}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(
    platform: models.Platform,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(
        select(models.SocialAccount).where(
            models.SocialAccount.user_id == user.id, models.SocialAccount.platform == platform
        )
    )
    if existing:
        await db.delete(existing)
        await db.commit()


@router.get("/{platform}/login")
async def login(
    platform: str,
    user: models.User = Depends(get_current_user_allow_query),
):
    """Reached from the profile page (see profile_router.py), not from a
    signup/login screen — connecting a platform never creates or authenticates
    an account by itself. The frontend links here as
    `/social/{platform}/login?token=<jwt>` — a plain browser navigation can't
    carry an Authorization header, so the already-issued access token rides
    in the query string. The signed `state` minted below is what actually
    secures the OAuth round trip; this query token only identifies who's
    connecting."""
    try:
        provider = get_provider(platform)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))

    code_verifier = secrets.token_urlsafe(64) if provider.USES_PKCE else None
    state = create_oauth_state_token(user.id, platform, code_verifier)
    return RedirectResponse(provider.authorize_url(state, code_verifier))


@router.get("/{platform}/callback")
async def callback(
    platform: str,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        provider = get_provider(platform)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))

    fail_url = f"{settings.frontend_origin}/profile?social={platform}&status=error"
    success_url = f"{settings.frontend_origin}/profile?social={platform}&status=ok"

    if error:
        return RedirectResponse(f"{fail_url}&reason={error_description or error}")

    state_payload = decode_oauth_state_token(state) if state else None
    if not code or not state_payload or state_payload.get("provider") != platform:
        return RedirectResponse(f"{fail_url}&reason=invalid_state")

    try:
        token = await provider.exchange_code(code, state_payload.get("code_verifier"))
    except OAuthError as exc:
        return RedirectResponse(f"{fail_url}&reason={exc}")

    user_id = uuid.UUID(state_payload["sub"])
    existing = await db.scalar(
        select(models.SocialAccount).where(
            models.SocialAccount.user_id == user_id, models.SocialAccount.platform == platform
        )
    )
    if existing:
        existing.access_token = token.access_token
        existing.refresh_token = token.refresh_token
        existing.platform_user_id = token.platform_user_id
        existing.expires_at = token.expires_at
    else:
        db.add(
            models.SocialAccount(
                user_id=user_id,
                platform=platform,
                platform_user_id=token.platform_user_id,
                access_token=token.access_token,
                refresh_token=token.refresh_token,
                expires_at=token.expires_at,
            )
        )
    await db.commit()

    return RedirectResponse(success_url)
