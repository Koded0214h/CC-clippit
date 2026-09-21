import logging
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
logger = logging.getLogger("clippit.social")
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
    """Reached from settings (or any already-signed-in screen), not from
    signup/login — connecting a platform never creates an account. The
    frontend navigates to `/social/{platform}/login?token=<jwt>` because a
    plain browser request can't carry an Authorization header. The signed
    `state` minted below secures the OAuth round trip; the query token only
    identifies who's connecting."""
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

    # FRONTEND_ORIGIN can be a comma-separated CORS list. The post-OAuth
    # redirect can only go to one URL — the first origin is the app itself.
    origin = settings.frontend_origin.split(",")[0].strip()
    fail_url = f"{origin}/dashboard/settings?social={platform}&status=error"
    success_url = f"{origin}/dashboard/settings?social={platform}&status=ok"

    if error:
        return RedirectResponse(f"{fail_url}&reason={error_description or error}")

    state_payload = decode_oauth_state_token(state) if state else None
    if not code or not state_payload or state_payload.get("provider") != platform:
        return RedirectResponse(f"{fail_url}&reason=invalid_state")

    try:
        token = await provider.exchange_code(code, state_payload.get("code_verifier"))
    except OAuthError as exc:
        return RedirectResponse(f"{fail_url}&reason={exc}")

    # Best effort: the connection is valid without a handle, so a failed
    # profile lookup is logged and the account is saved anyway.
    profile = None
    fetch_profile = getattr(provider, "fetch_profile", None)
    if fetch_profile is not None:
        try:
            profile = await fetch_profile(token.access_token, token.platform_user_id)
        except Exception:  # noqa: BLE001
            logger.warning("could not read %s profile after connect", platform, exc_info=True)
    handle = profile.handle if profile else None
    display_name = profile.display_name if profile else None

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
        existing.handle = handle or existing.handle
        existing.display_name = display_name or existing.display_name
        existing.expires_at = token.expires_at
    else:
        db.add(
            models.SocialAccount(
                user_id=user_id,
                platform=platform,
                platform_user_id=token.platform_user_id,
                handle=handle,
                display_name=display_name,
                access_token=token.access_token,
                refresh_token=token.refresh_token,
                expires_at=token.expires_at,
            )
        )
    await db.commit()

    return RedirectResponse(success_url)
