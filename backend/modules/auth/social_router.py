import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

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
def list_accounts(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    accounts = db.query(models.SocialAccount).filter(models.SocialAccount.user_id == user.id).all()
    return [schemas.SocialAccountOut.from_model(a) for a in accounts]


@router.delete("/{platform}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(
    platform: models.Platform,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(models.SocialAccount).filter(
        models.SocialAccount.user_id == user.id,
        models.SocialAccount.platform == platform,
    ).delete()
    db.commit()


@router.get("/{platform}/login")
def login(
    platform: str,
    user: models.User = Depends(get_current_user_allow_query),
):
    """The frontend links here as `/social/{platform}/login?token=<jwt>` —
    a plain browser navigation can't carry an Authorization header, so the
    already-issued access token rides in the query string instead. The
    state token minted below is what actually protects the round trip;
    this query token is short-lived and only identifies who's connecting."""
    try:
        provider = get_provider(platform)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))

    code_verifier = secrets.token_urlsafe(64) if provider.USES_PKCE else None
    state = create_oauth_state_token(user.id, platform, code_verifier)
    return RedirectResponse(provider.authorize_url(state, code_verifier))


@router.get("/{platform}/callback")
def callback(
    platform: str,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        provider = get_provider(platform)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))

    fail_url = f"{settings.frontend_origin}/auth/social-connected?platform={platform}&status=error"
    success_url = f"{settings.frontend_origin}/auth/social-connected?platform={platform}&status=ok"

    if error:
        return RedirectResponse(f"{fail_url}&reason={error_description or error}")

    state_payload = decode_oauth_state_token(state) if state else None
    if not code or not state_payload or state_payload.get("provider") != platform:
        return RedirectResponse(f"{fail_url}&reason=invalid_state")

    try:
        token = provider.exchange_code(code, state_payload.get("code_verifier"))
    except OAuthError as exc:
        return RedirectResponse(f"{fail_url}&reason={exc}")

    user_id = uuid.UUID(state_payload["sub"])
    existing = (
        db.query(models.SocialAccount)
        .filter(models.SocialAccount.user_id == user_id, models.SocialAccount.platform == platform)
        .first()
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
    db.commit()

    return RedirectResponse(success_url)
