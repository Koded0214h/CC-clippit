import hashlib
import logging
import secrets
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.deps import get_db
from core.meta_webhooks import InvalidSignedRequest, parse_signed_request
from core.security import create_oauth_state_token, decode_oauth_state_token

from . import models, schemas
from .deps import get_current_user, get_current_user_allow_query
from .providers import get_provider
from .providers.base import OAuthError

router = APIRouter(prefix="/social", tags=["social"])
webhook_router = APIRouter(prefix="/webhooks/social", tags=["social"])
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
    origin = settings.app_url
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


# --- token refresh / profile sync (production-api-inventory.md §F) -----------


@router.post("/{platform}/refresh")
async def refresh_account(
    platform: str, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Only TikTok's adapter has a real refresh grant today (see
    `providers.tiktok.refresh`'s docstring) — Meta's tokens are already
    long-lived with no server-side refresh, and X has none wired here.
    Everyone else gets `reconnect_required` rather than a 501, so the
    caller (normally a worker, per the inventory) has one shape to
    handle either way."""
    try:
        provider = get_provider(platform)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    account = await db.scalar(
        select(models.SocialAccount).where(models.SocialAccount.user_id == user.id, models.SocialAccount.platform == platform)
    )
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No connected {platform} account.")

    refresh = getattr(provider, "refresh", None)
    if refresh is None or not account.refresh_token:
        return {"reconnect_required": True, "reason": "This platform has no automatic refresh; reconnect it."}

    try:
        token = await refresh(account.refresh_token)
    except OAuthError as exc:
        return {"reconnect_required": True, "reason": str(exc)}

    account.access_token = token.access_token
    account.refresh_token = token.refresh_token or account.refresh_token
    account.expires_at = token.expires_at
    await db.commit()
    return {"reconnect_required": False, "expires_at": token.expires_at}


@router.post("/{platform}/sync-profile", response_model=schemas.SocialAccountOut)
async def sync_profile(
    platform: str, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Re-reads the connected handle/display name — the same lookup
    `callback` does right after connecting, run again on demand (a
    creator renamed their TikTok, or the initial lookup failed)."""
    try:
        provider = get_provider(platform)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    account = await db.scalar(
        select(models.SocialAccount).where(models.SocialAccount.user_id == user.id, models.SocialAccount.platform == platform)
    )
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No connected {platform} account.")

    fetch_profile = getattr(provider, "fetch_profile", None)
    if fetch_profile is not None:
        try:
            profile = await fetch_profile(account.access_token, account.platform_user_id)
        except Exception:  # noqa: BLE001
            logger.warning("could not resync %s profile", platform, exc_info=True)
            profile = None
        if profile is not None:
            account.handle = profile.handle or account.handle
            account.display_name = profile.display_name or account.display_name
            await db.commit()
    return schemas.SocialAccountOut.from_model(account)


# --- platform-initiated webhooks ----------------------------------------------
# Deauthorize/data-deletion callbacks — Meta's `signed_request` format (see
# core.meta_webhooks). Unverified against real Meta traffic; TikTok/X have
# no equivalent callback wired here.

_META_APP_SECRETS = {
    "facebook": lambda s: s.facebook_app_secret,
    "instagram": lambda s: s.instagram_app_secret,
    "threads": lambda s: s.threads_app_secret,
}


async def _verify_meta_callback(platform: str, signed_request: str) -> dict:
    secret_getter = _META_APP_SECRETS.get(platform)
    if secret_getter is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No signed-webhook contract for {platform}.")
    secret = secret_getter(get_settings())
    if not secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"{platform} isn't configured.")
    try:
        return parse_signed_request(signed_request, secret)
    except InvalidSignedRequest as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


@webhook_router.post("/{platform}/deauthorize", include_in_schema=False)
async def deauthorize(platform: str, signed_request: str = Form(...), db: AsyncSession = Depends(get_db)):
    """The platform user removed Clippit's access on their end — disconnect
    our side too, since their token is already dead."""
    payload = await _verify_meta_callback(platform, signed_request)
    platform_user_id = str(payload.get("user_id", ""))
    if platform_user_id:
        account = await db.scalar(
            select(models.SocialAccount).where(
                models.SocialAccount.platform == platform, models.SocialAccount.platform_user_id == platform_user_id
            )
        )
        if account:
            await db.delete(account)
            await db.commit()
    return {"received": True}


@webhook_router.post("/{platform}/data-deletion", include_in_schema=False)
async def data_deletion(request: Request, platform: str, signed_request: str = Form(...), db: AsyncSession = Depends(get_db)):
    """Meta's required response shape: a status-check URL and a
    confirmation code the platform user can quote to us."""
    payload = await _verify_meta_callback(platform, signed_request)
    platform_user_id = str(payload.get("user_id", ""))
    confirmation_code = hashlib.sha256(f"{platform}:{platform_user_id}:{secrets.token_hex(8)}".encode()).hexdigest()[:16]
    if platform_user_id:
        account = await db.scalar(
            select(models.SocialAccount).where(
                models.SocialAccount.platform == platform, models.SocialAccount.platform_user_id == platform_user_id
            )
        )
        if account:
            await db.delete(account)
            await db.commit()
    origin = get_settings().app_url
    return {"url": f"{origin}/data-deletion-status?code={confirmation_code}", "confirmation_code": confirmation_code}
