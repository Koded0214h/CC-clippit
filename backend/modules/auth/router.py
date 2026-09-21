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
    create_access_token,
    create_purpose_token,
    decode_access_token,
    decode_purpose_token,
    hash_password,
    verify_password,
)

from . import codes, emails, models, schemas
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
    await db.commit()
    await db.refresh(user)

    await _deliver(sender, emails.verification_email(user.email, code))

    token = create_access_token(user.id, user.role.value)
    return schemas.TokenResponse(access_token=token, user=schemas.UserOut.model_validate(user))


@router.post("/login", response_model=schemas.TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, payload: schemas.LoginRequest, db: AsyncSession = Depends(get_db)):
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    user = await _user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise invalid

    token = create_access_token(user.id, user.role.value)
    return schemas.TokenResponse(access_token=token, user=schemas.UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user: models.User = Depends(get_current_user),
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Revokes only the token used to call this endpoint — every other
    token this user holds (another device, another tab) stays valid. See
    modules.auth.models.RevokedToken."""
    payload = decode_access_token(token) if token else None
    jti = payload.get("jti") if payload else None
    if jti and not await db.get(models.RevokedToken, jti):
        db.add(
            models.RevokedToken(
                jti=jti,
                expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            )
        )
        await db.commit()


@router.get("/me", response_model=schemas.UserOut)
async def me(user: models.User = Depends(get_current_user)):
    return schemas.UserOut.model_validate(user)


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
    await _deliver(sender, emails.verification_email(user.email, code))
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
    user.tokens_valid_after = now
    if not user.email_verified:
        # They just proved control of the inbox.
        user.email_verified = True
        user.email_verified_at = now
    # Single use: spend the token so it can't set the password twice.
    db.add(models.RevokedToken(jti=claims["jti"], expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc)))
    await db.commit()
