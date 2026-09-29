"""`GET /auth/google/login` and `/auth/google/callback` — sign up, sign
in, or link with a Google account. See `modules.auth.google` for the
OIDC mechanics and why verification goes through `tokeninfo`.
"""

import logging
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.deps import get_db
from core.security import (
    create_google_pending_signup_token,
    create_google_state_token,
    decode_google_pending_signup_token,
    decode_google_state_token,
    hash_password,
)

from . import models, schemas, sessions
from .deps import get_current_user
from .google import GoogleAuthError, exchange_code, verify_id_token

router = APIRouter(prefix="/auth/google", tags=["auth"])
logger = logging.getLogger("clippit.auth.google")


@router.get("/login")
async def google_login(
    role: models.Role | None = Query(None, description="Only meaningful for a new account"),
):
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in isn't configured yet.")
    nonce = secrets.token_urlsafe(24)
    state = create_google_state_token(nonce=nonce, intent="login", role=role.value if role else None, link_user_id=None)
    from .google import authorize_url

    return RedirectResponse(authorize_url(state, nonce))


@router.get("/link")
async def google_link_start(user: models.User = Depends(get_current_user)):
    """Attach Google to the signed-in account rather than creating or
    signing in to one — same callback, a different `intent`."""
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in isn't configured yet.")
    nonce = secrets.token_urlsafe(24)
    state = create_google_state_token(nonce=nonce, intent="link", role=None, link_user_id=user.id)
    from .google import authorize_url

    return RedirectResponse(authorize_url(state, nonce))


@router.get("/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    origin = settings.app_url
    fail = lambda reason: RedirectResponse(f"{origin}/auth/sign-in?google_error={reason}")  # noqa: E731

    if error:
        return fail(error)
    state_payload = decode_google_state_token(state) if state else None
    if not code or not state_payload:
        return fail("invalid_state")

    try:
        id_token = await exchange_code(code)
        identity = await verify_id_token(id_token, expected_nonce=state_payload["nonce"])
    except GoogleAuthError as exc:
        return fail(str(exc))

    intent = state_payload.get("intent")

    if intent == "link":
        link_user_id = state_payload.get("link_user_id")
        if not link_user_id:
            return fail("invalid_state")
        taken = await db.scalar(select(models.User.id).where(models.User.google_id == identity.google_id))
        if taken and str(taken) != link_user_id:
            return fail("google_account_already_linked")
        user = await db.get(models.User, uuid.UUID(link_user_id))
        if user is None:
            return fail("invalid_state")
        user.google_id = identity.google_id
        user.google_email = identity.email
        await db.commit()
        return RedirectResponse(f"{origin}/dashboard/security?google=linked")

    # intent == "login": sign in to an existing Google-linked account,
    # auto-link a verified-email match, or create a new one.
    user = await db.scalar(select(models.User).where(models.User.google_id == identity.google_id))
    email_owner = None if user else await db.scalar(select(models.User).where(models.User.email == identity.email))
    if user is None and email_owner is not None:
        # Only auto-link onto an *existing* account when Google itself
        # vouches for the email — otherwise this would be exactly the
        # account-takeover-by-email hole the inventory calls out. An
        # email that exists here but isn't Google-verified, or is already
        # linked to a *different* Google account, is refused outright
        # rather than silently spun into a second, colliding account.
        if not identity.email_verified:
            return fail("email_not_verified_by_google")
        if email_owner.google_id is not None:
            return fail("email_already_registered")
        email_owner.google_id = identity.google_id
        email_owner.google_email = identity.email
        user = email_owner

    if user is None:
        role = state_payload.get("role")
        if role is None:
            # The sign-in page's Google button never sends a role (correct
            # for an existing user). For a genuinely new account this is
            # ambiguous — guessing here would silently, permanently stamp
            # the wrong role, so ask instead of defaulting to creator.
            pending = create_google_pending_signup_token(
                google_id=identity.google_id, email=identity.email,
                name=identity.name, email_verified=identity.email_verified,
            )
            return RedirectResponse(f"{origin}/auth/choose-role?token={pending}")
        if role == models.Role.admin.value:
            return fail("cannot_sign_up_as_admin")
        user = models.User(
            email=identity.email,
            password_hash=hash_password(secrets.token_urlsafe(32)),  # unusable placeholder — see User.has_password
            has_password=False,
            full_name=identity.name or identity.email.split("@")[0],
            role=models.Role(role),
            google_id=identity.google_id,
            google_email=identity.email,
            email_verified=identity.email_verified,
        )
        db.add(user)
        await db.flush()
        db.add(models.UserPreferences(user_id=user.id))

    if user.deleted_at is not None:
        return fail("account_deleted")

    issued = await sessions.start_session(db, user, request)
    await db.commit()
    if not user.onboarding_completed:
        dest = "/brand" if user.role == models.Role.organisation else "/onboarding/creator"
    else:
        dest = "/brand" if user.role == models.Role.organisation else "/dashboard"
    return RedirectResponse(
        f"{origin}/auth/success?access_token={issued.access_token}&refresh_token={issued.refresh_token}&next={dest}"
    )


class ChooseRoleBody(BaseModel):
    token: str
    role: models.Role


@router.post("/complete-signup", response_model=schemas.TokenResponse)
async def complete_pending_signup(
    body: ChooseRoleBody, request: Request, db: AsyncSession = Depends(get_db),
):
    """Finishes a Google signup that `/callback` parked at `/auth/choose-role`
    because it had no role to create the account with. Re-verifies nothing
    with Google — the identity was already verified once; this only spends
    the short-lived pending token and applies the role the person picked."""
    if body.role == models.Role.admin:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cannot sign up as admin.")
    pending = decode_google_pending_signup_token(body.token)
    if not pending:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This link has expired. Try signing in again.")

    user = await db.scalar(select(models.User).where(models.User.google_id == pending["google_id"]))
    if user is None:
        existing_email = await db.scalar(select(models.User).where(models.User.email == pending["email"]))
        if existing_email is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
        user = models.User(
            email=pending["email"],
            password_hash=hash_password(secrets.token_urlsafe(32)),
            has_password=False,
            full_name=pending["name"] or pending["email"].split("@")[0],
            role=body.role,
            google_id=pending["google_id"],
            google_email=pending["email"],
            email_verified=pending["email_verified"],
        )
        db.add(user)
        await db.flush()
        db.add(models.UserPreferences(user_id=user.id))

    if user.deleted_at is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account was deleted.")

    issued = await sessions.start_session(db, user, request)
    await db.commit()
    await db.refresh(user)
    return schemas.TokenResponse(
        access_token=issued.access_token, refresh_token=issued.refresh_token, user=schemas.UserOut.model_validate(user)
    )
