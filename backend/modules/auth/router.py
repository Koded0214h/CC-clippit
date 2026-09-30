import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.deps import get_db
from core.email import EmailSender, get_email_sender
from core.rate_limit import limiter
from core.security import (
    create_purpose_token,
    decode_access_token,
    decode_admin_invite_token,
    decode_purpose_token,
    hash_password,
    verify_password,
)

from . import codes, emails, models, schemas, sessions
from .deps import get_current_user, get_optional_user, oauth2_scheme

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("clippit.auth")

RESET_TOKEN_MINUTES = 15


async def _deliver(sender: EmailSender, message) -> None:
    """A failed email must not fail the request that triggered it — the user
    can ask for another code. It must not be silent either."""
    try:
        await sender.send(message)
    except Exception:  # noqa: BLE001
        logger.exception("could not send email to %s", message.to)


async def _user_by_email(db: AsyncSession, email: str) -> models.User | None:
    return await db.scalar(select(models.User).where(models.User.email == email))


@router.post("/signup", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def signup(
    request: Request,
    payload: schemas.SignupRequest,
    db: AsyncSession = Depends(get_db),
    sender: EmailSender = Depends(get_email_sender),
):
    if await _user_by_email(db, payload.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")

    user = models.User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(user)
    await db.flush()  # assigns user.id (client-side default) without committing yet
    db.add(models.UserPreferences(user_id=user.id))
    code = await codes.issue_code(db, user, models.AuthCodePurpose.email_verify)
    issued = await sessions.start_session(db, user, request)
    await db.commit()
    await db.refresh(user)

    await _deliver(sender, emails.verification_email(user.email, code, user.role.value))

    return schemas.TokenResponse(
        access_token=issued.access_token, refresh_token=issued.refresh_token, user=schemas.UserOut.model_validate(user)
    )


@router.post("/login", response_model=schemas.TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, payload: schemas.LoginRequest, db: AsyncSession = Depends(get_db)):
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    user = await _user_by_email(db, payload.email)
    if not user or user.deleted_at is not None or not user.has_password or not verify_password(payload.password, user.password_hash):
        raise invalid

    issued = await sessions.start_session(db, user, request)
    await db.commit()
    return schemas.TokenResponse(
        access_token=issued.access_token, refresh_token=issued.refresh_token, user=schemas.UserOut.model_validate(user)
    )


@router.post("/admin/login", response_model=schemas.TokenResponse)
@limiter.limit("5/minute")
async def admin_login(request: Request, payload: schemas.LoginRequest, db: AsyncSession = Depends(get_db)):
    """Only active operators may create a session through the admin sign-in."""
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password, or no administrator access.")
    user = await _user_by_email(db, payload.email)
    if (
        not user or user.deleted_at is not None or not user.has_password
        or not verify_password(payload.password, user.password_hash)
        or user.role != models.Role.admin
        or (user.suspended_at is not None and "access" in user.suspension_scopes)
    ):
        raise invalid
    issued = await sessions.start_session(db, user, request)
    await db.commit()
    return schemas.TokenResponse(
        access_token=issued.access_token, refresh_token=issued.refresh_token, user=schemas.UserOut.model_validate(user)
    )


@router.post("/refresh", response_model=schemas.TokenResponse)
@limiter.limit("30/minute")
async def refresh(request: Request, payload: schemas.RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        issued = await sessions.rotate(db, payload.refresh_token)
    except sessions.RefreshError as exc:
        await db.commit()  # persist a reuse-detected revocation even though the call itself fails
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, exc.message) from exc
    user = await db.get(models.User, issued.session.user_id)
    await db.commit()
    return schemas.TokenResponse(
        access_token=issued.access_token, refresh_token=issued.refresh_token, user=schemas.UserOut.model_validate(user)
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user: models.User = Depends(get_current_user),
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Revokes only the token used to call this endpoint — every other
    token this user holds (another device, another tab) stays valid. See
    modules.auth.models.RevokedToken. Also revokes the underlying session,
    so its refresh token can't mint a new access token either."""
    payload = decode_access_token(token) if token else None
    jti = payload.get("jti") if payload else None
    if jti and not await db.get(models.RevokedToken, jti):
        db.add(
            models.RevokedToken(
                jti=jti,
                expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            )
        )
    sid = payload.get("sid") if payload else None
    if sid:
        await sessions.revoke_session(db, user.id, uuid.UUID(sid))
    await db.commit()


# --- sessions ----------------------------------------------------------------


def _session_out(session: models.Session, current_id: uuid.UUID | None) -> schemas.SessionOut:
    return schemas.SessionOut(
        id=session.id,
        device_label=session.device_label,
        ip_address=session.ip_address,
        created_at=session.created_at,
        last_seen_at=session.last_seen_at,
        remembered=session.remembered_at is not None,
        current=session.id == current_id,
    )


@router.get("/sessions", response_model=list[schemas.SessionOut])
async def list_sessions(
    user: models.User = Depends(get_current_user),
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    payload = decode_access_token(token) if token else None
    current_id = uuid.UUID(payload["sid"]) if payload and payload.get("sid") else None
    rows = await sessions.list_sessions(db, user.id)
    return [_session_out(s, current_id) for s in rows]


@router.delete("/sessions/others", response_model=schemas.RevokedCountOut)
async def revoke_other_sessions(
    user: models.User = Depends(get_current_user),
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    payload = decode_access_token(token) if token else None
    current_id = uuid.UUID(payload["sid"]) if payload and payload.get("sid") else None
    count = await sessions.revoke_other_sessions(db, user.id, current_id)
    await db.commit()
    return schemas.RevokedCountOut(revoked=count)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_one_session(
    session_id: uuid.UUID,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await sessions.revoke_session(db, user.id, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    await db.commit()


@router.get("/me", response_model=schemas.UserOut)
async def me(user: models.User = Depends(get_current_user)):
    return schemas.UserOut.model_validate(user)


@router.patch("/me", response_model=schemas.UserOut)
async def update_me(
    payload: schemas.AccountUpdate,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The account holder's own display name (operators have no profile
    record, so this is the only place theirs can be changed)."""
    user.full_name = payload.full_name
    await db.commit()
    await db.refresh(user)
    return schemas.UserOut.model_validate(user)


# --- remembered devices -----------------------------------------------------


def _session_id_from_token(token: str | None) -> uuid.UUID | None:
    payload = decode_access_token(token) if token else None
    sid = payload.get("sid") if payload else None
    try:
        return uuid.UUID(sid) if sid else None
    except (TypeError, ValueError):
        return None


@router.post("/remember-device/request", response_model=schemas.CodeSentResponse)
@limiter.limit("6/minute")
async def request_remember_device(
    request: Request,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sender: EmailSender = Depends(get_email_sender),
):
    if not user.email_verified:
        raise HTTPException(status.HTTP_409_CONFLICT, "Confirm your email before remembering this device.")

    cooldown = get_settings().otp_resend_cooldown_seconds
    try:
        code = await codes.issue_code(db, user, models.AuthCodePurpose.remember_device)
    except codes.CooldownActive as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            exc.message,
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    await db.commit()
    await _deliver(sender, emails.remember_device_email(user.email, code))
    return schemas.CodeSentResponse(resend_in=cooldown)


@router.post("/remember-device/verify", response_model=schemas.RememberDeviceOut)
@limiter.limit("10/minute")
async def verify_remember_device(
    request: Request,
    payload: schemas.RememberDeviceVerifyRequest,
    user: models.User = Depends(get_current_user),
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    session_id = _session_id_from_token(token)
    if session_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This session cannot be remembered. Sign in again.")

    try:
        await codes.check_code(db, user, models.AuthCodePurpose.remember_device, payload.code)
    except codes.CodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message) from exc

    session = await sessions.remember_session(db, user.id, session_id)
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This session is no longer active. Sign in again.")
    await db.commit()
    return schemas.RememberDeviceOut(expires_in_days=sessions.REMEMBERED_REFRESH_TOKEN_DAYS)


# --- Email verification -----------------------------------------------------


async def _resolve_user(
    db: AsyncSession, session_user: models.User | None, email: str | None
) -> models.User | None:
    if session_user is not None:
        return session_user
    return await _user_by_email(db, email) if email else None


@router.post("/verify-email", response_model=schemas.UserOut)
@limiter.limit("10/minute")
async def verify_email(
    request: Request,
    payload: schemas.VerifyEmailRequest,
    session_user: models.User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Works signed in (the normal path — the token from signup) or with just
    `email` + `code` (the verify page opened on another device)."""
    user = await _resolve_user(db, session_user, payload.email)
    if user is None:
        # Same answer as a wrong code: don't reveal which emails exist.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That code isn't right or has expired. Ask for a new one.")
    if user.email_verified:
        return schemas.UserOut.model_validate(user)

    try:
        await codes.check_code(db, user, models.AuthCodePurpose.email_verify, payload.code)
    except codes.CodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message) from exc

    user.email_verified = True
    user.email_verified_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return schemas.UserOut.model_validate(user)


@router.post("/verify-email/resend", response_model=schemas.CodeSentResponse)
@limiter.limit("6/minute")
async def resend_verification(
    request: Request,
    payload: schemas.ResendCodeRequest,
    session_user: models.User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
    sender: EmailSender = Depends(get_email_sender),
):
    cooldown = get_settings().otp_resend_cooldown_seconds
    user = await _resolve_user(db, session_user, payload.email)
    if user is None:
        return schemas.CodeSentResponse(resend_in=cooldown)  # no enumeration
    if user.email_verified:
        raise HTTPException(status.HTTP_409_CONFLICT, "This email address is already confirmed.")

    try:
        code = await codes.issue_code(db, user, models.AuthCodePurpose.email_verify)
    except codes.CooldownActive as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, exc.message, headers={"Retry-After": str(exc.retry_after)}
        ) from exc
    await db.commit()
    await _deliver(sender, emails.verification_email(user.email, code, user.role.value))
    return schemas.CodeSentResponse(resend_in=cooldown)


# --- Password recovery ------------------------------------------------------


@router.post("/forgot-password", response_model=schemas.CodeSentResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    payload: schemas.ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    sender: EmailSender = Depends(get_email_sender),
):
    """Always answers the same way whether or not the email has an account,
    so this can't be used to find out who is registered."""
    cooldown = get_settings().otp_resend_cooldown_seconds
    user = await _user_by_email(db, payload.email)
    if user is not None:
        try:
            code = await codes.issue_code(db, user, models.AuthCodePurpose.password_reset)
        except codes.CooldownActive:
            pass  # a code was just sent; say nothing different
        else:
            await db.commit()
            await _deliver(sender, emails.recovery_email(user.email, code))
    return schemas.CodeSentResponse(resend_in=cooldown)


@router.post("/recovery-code/verify", response_model=schemas.ResetTokenResponse)
@limiter.limit("10/minute")
async def verify_recovery_code(
    request: Request, payload: schemas.RecoveryCodeRequest, db: AsyncSession = Depends(get_db)
):
    user = await _user_by_email(db, payload.email)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That code isn't right or has expired. Ask for a new one.")
    try:
        await codes.check_code(db, user, models.AuthCodePurpose.password_reset, payload.code)
    except codes.CodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message) from exc
    await db.commit()
    return schemas.ResetTokenResponse(
        reset_token=create_purpose_token(user.id, "password_reset", RESET_TOKEN_MINUTES)
    )


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def reset_password(
    request: Request, payload: schemas.ResetPasswordRequest, db: AsyncSession = Depends(get_db)
):
    invalid = HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link has expired. Start again.")
    claims = decode_purpose_token(payload.reset_token, "password_reset")
    if not claims or await db.get(models.RevokedToken, claims["jti"]):
        raise invalid

    user = await db.get(models.User, uuid.UUID(claims["sub"]))
    if user is None:
        raise invalid

    now = datetime.now(timezone.utc)
    user.password_hash = hash_password(payload.password)
    user.has_password = True
    user.tokens_valid_after = now
    if not user.email_verified:
        # They just proved control of the inbox.
        user.email_verified = True
        user.email_verified_at = now
    # Single use: spend the token so it can't set the password twice.
    db.add(models.RevokedToken(jti=claims["jti"], expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc)))
    await db.commit()


# --- security settings: password, providers, step-up, account lifecycle ------


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    payload: schemas.ChangePasswordRequest,
    user: models.User = Depends(get_current_user),
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    if not user.has_password or not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect.")
    user.password_hash = hash_password(payload.new_password)
    if payload.revoke_other_sessions:
        session_payload = decode_access_token(token) if token else None
        current_id = uuid.UUID(session_payload["sid"]) if session_payload and session_payload.get("sid") else None
        await sessions.revoke_other_sessions(db, user.id, current_id)
    await db.commit()


def _step_up_challenge_purpose(action: str) -> str:
    return f"step_up_challenge:{action}"


def _step_up_purpose(action: str) -> str:
    return f"step_up:{action}"


@router.post("/step-up/request", response_model=schemas.StepUpChallengeOut)
@limiter.limit("10/minute")
async def request_step_up(
    request: Request,
    payload: schemas.StepUpRequestIn,
    user: models.User = Depends(get_current_user),
):
    """Starts a sensitive-action challenge. Today the only verified factor
    an account has is its password, so this mints a short-lived challenge
    token binding *who* and *which action* — `verify` below is what
    actually checks the password. Once 2FA exists, this is where the
    choice of factor (TOTP vs. recovery code) would be offered."""
    minutes = 5
    return schemas.StepUpChallengeOut(
        challenge_token=create_purpose_token(user.id, _step_up_challenge_purpose(payload.action), minutes),
        expires_in=minutes * 60,
    )


@router.post("/step-up/verify", response_model=schemas.StepUpTokenOut)
@limiter.limit("10/minute")
async def verify_step_up(
    request: Request,
    payload: schemas.StepUpVerifyIn,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    claims = decode_access_token(payload.challenge_token)
    purpose = claims.get("purpose") if claims else None
    if not claims or not purpose or not purpose.startswith("step_up_challenge:") or claims.get("sub") != str(user.id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This challenge has expired. Start again.")
    if await db.get(models.RevokedToken, claims["jti"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This challenge has already been used.")
    if not user.has_password or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect password.")

    action = purpose.removeprefix("step_up_challenge:")
    db.add(models.RevokedToken(jti=claims["jti"], expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc)))
    await db.commit()
    minutes = 5
    return schemas.StepUpTokenOut(
        step_up_token=create_purpose_token(user.id, _step_up_purpose(action), minutes),
        action=action,
        expires_in=minutes * 60,
    )


async def consume_step_up(db: AsyncSession, token: str, action: str, user_id: uuid.UUID) -> None:
    """Spends a step-up token for exactly the action it names. Raises a 401
    if it's missing, wrong-action, someone else's, or already spent."""
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Recent verification required — request a new one.")
    claims = decode_purpose_token(token, _step_up_purpose(action))
    if not claims or claims.get("sub") != str(user_id):
        raise invalid
    if await db.get(models.RevokedToken, claims["jti"]):
        raise invalid
    db.add(models.RevokedToken(jti=claims["jti"], expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc)))


@router.get("/providers", response_model=schemas.ProvidersOut)
async def list_providers(user: models.User = Depends(get_current_user)):
    return schemas.ProvidersOut(
        providers=[
            schemas.ProviderStatus(
                provider="password", linked=user.has_password, removable=user.google_id is not None
            ),
            schemas.ProviderStatus(
                provider="google", linked=user.google_id is not None, removable=user.has_password,
                email=user.google_email,
            ),
        ]
    )


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def set_first_password(
    payload: schemas.SetPasswordRequest,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """A provider-only account (Google, no password yet) sets one for the
    first time. Use `/change-password` once one already exists."""
    if user.has_password:
        raise HTTPException(status.HTTP_409_CONFLICT, "This account already has a password — use change-password.")
    await consume_step_up(db, payload.step_up_token, "set_password", user.id)
    user.password_hash = hash_password(payload.password)
    user.has_password = True
    await db.commit()


@router.delete("/providers/google", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_google(
    payload: schemas.StepUpOnly,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.google_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No Google account is linked.")
    if not user.has_password:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Set a password first — removing Google would leave no way to sign in."
        )
    await consume_step_up(db, payload.step_up_token, "unlink_google", user.id)
    user.google_id = None
    user.google_email = None
    await db.commit()


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    payload: schemas.StepUpOnly,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Anonymises rather than hard-deletes: campaigns, submissions and
    ledger rows keep a valid (now-anonymous) foreign key, and finance
    history that must be retained survives. Refuses while money that
    traces back to this account is still unsettled."""
    await consume_step_up(db, payload.step_up_token, "delete_account", user.id)

    if user.role == models.Role.creator:
        from modules.earnings.queries import balances

        b = await balances(db, user.id)
        if b.payable > 0 or b.in_hold > 0 or b.processing > 0:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "You have money that hasn't been paid out yet. Withdraw it first, then delete your account.",
            )
    elif user.role == models.Role.organisation:
        from sqlalchemy import select as _select

        from modules.campaigns.models import Campaign, CampaignStatus

        unresolved = await db.scalar(
            _select(Campaign.id).where(
                Campaign.event_manager_id == user.id,
                Campaign.status.in_((CampaignStatus.pending_funding, CampaignStatus.active)),
            )
        )
        if unresolved:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "You have a campaign that's funding or live. Close it first, then delete your account.",
            )

    now = datetime.now(timezone.utc)
    user.deleted_at = now
    user.tokens_valid_after = now
    user.email = f"deleted-{user.id}@deleted.clippit.invalid"
    user.full_name = "Deleted user"
    user.password_hash = hash_password(uuid.uuid4().hex)
    user.has_password = False
    user.google_id = None
    user.google_email = None
    await db.execute(
        models.SocialAccount.__table__.delete().where(models.SocialAccount.user_id == user.id)
    )
    await sessions.revoke_other_sessions(db, user.id, keep_session_id=None)
    from modules.audit import service as audit

    audit.record(db, "account.deleted", actor_id=user.id)
    await db.commit()


# --- operator invitations and permissions (production-api-inventory.md §O) ----


@router.get("/permissions", response_model=schemas.PermissionsOut)
async def my_permissions(user: models.User = Depends(get_current_user)):
    """One truth for admin UI and API enforcement to share — though today
    only this read exists; individual admin routes don't check it yet
    (see the inventory note on `POST /admin/operators/invitations`)."""
    if user.role != models.Role.admin:
        return schemas.PermissionsOut(permissions=[])
    return schemas.PermissionsOut(permissions=list(user.permissions) or ["*"])


@router.get("/admin-invitations/{token}", response_model=schemas.AdminInvitationStatus)
async def invitation_status(token: str, db: AsyncSession = Depends(get_db)):
    invitation_id = decode_admin_invite_token(token)
    if invitation_id is None:
        return schemas.AdminInvitationStatus(status="invalid")
    invitation = await db.get(models.OperatorInvitation, invitation_id)
    if invitation is None:
        return schemas.AdminInvitationStatus(status="invalid")
    if invitation.accepted_at is not None:
        return schemas.AdminInvitationStatus(status="used")
    if invitation.expires_at < datetime.now(timezone.utc):
        return schemas.AdminInvitationStatus(status="expired")
    return schemas.AdminInvitationStatus(status="valid", email=invitation.email, permissions=list(invitation.permissions))


@router.post("/admin-invitations/{token}/accept", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def accept_invitation(
    request: Request, token: str, payload: schemas.AdminInvitationAccept, db: AsyncSession = Depends(get_db)
):
    invalid = HTTPException(status.HTTP_400_BAD_REQUEST, "This invitation isn't valid anymore.")
    invitation_id = decode_admin_invite_token(token)
    if invitation_id is None:
        raise invalid
    invitation = await db.get(models.OperatorInvitation, invitation_id)
    if invitation is None or invitation.accepted_at is not None or invitation.expires_at < datetime.now(timezone.utc):
        raise invalid
    if await _user_by_email(db, invitation.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")

    user = models.User(
        email=invitation.email, password_hash=hash_password(payload.password), full_name=payload.full_name,
        role=models.Role.admin, email_verified=True, permissions=invitation.permissions, invited_by=invitation.invited_by,
    )
    db.add(user)
    await db.flush()
    db.add(models.UserPreferences(user_id=user.id))
    invitation.accepted_at = datetime.now(timezone.utc)
    invitation.accepted_user_id = user.id
    from modules.audit import service as audit

    audit.record(db, "admin.operator_invitation_accepted", actor_id=user.id, subject_id=invitation.invited_by)
    issued = await sessions.start_session(db, user, request)
    await db.commit()
    await db.refresh(user)
    return schemas.TokenResponse(access_token=issued.access_token, refresh_token=issued.refresh_token, user=schemas.UserOut.model_validate(user))
