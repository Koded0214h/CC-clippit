import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.deps import get_db
from core.security import decode_access_token

from . import models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> models.User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    if not token:
        raise unauthorized
    payload = decode_access_token(token)
    if not payload or payload.get("purpose") == "oauth_state":
        raise unauthorized

    jti = payload.get("jti")
    if jti and await db.get(models.RevokedToken, jti):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This token has been logged out")

    sid = payload.get("sid")
    if sid:
        session = await db.get(models.Session, uuid.UUID(sid))
        if session is None or session.revoked_at is not None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This session has been signed out")

    user = await db.get(models.User, uuid.UUID(payload["sub"]))
    if not user or user.deleted_at is not None:
        raise unauthorized
    if user.suspended_at is not None and "access" in user.suspension_scopes:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "account_suspended", "message": "This account has been suspended.", "reason": user.suspension_reason},
        )
    if user.tokens_valid_after is not None:
        issued = payload.get("iat")
        # A token with no `iat` predates this check; after a password reset
        # it is treated as stale rather than trusted.
        # `iat` has one-second resolution, so compare at that resolution — a
        # sign-in in the same second as the reset must keep working.
        if issued is None or int(issued) < int(user.tokens_valid_after.timestamp()):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired — sign in again")
    return user


async def get_optional_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> models.User | None:
    """The signed-in user if there is a valid session, else None. For the
    handful of endpoints that work either way (verify-email)."""
    if not token:
        return None
    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None


async def get_verified_user(user: models.User = Depends(get_current_user)) -> models.User:
    """A signed-in user whose email is confirmed. Guards everything that
    spends, earns or publishes — the actions where an unconfirmed address
    is a real problem."""
    if get_settings().require_email_verification and not user.email_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "email_not_verified", "message": "Confirm your email address first."},
        )
    return user


async def get_current_user_allow_query(
    token: str | None = None,
    bearer_token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> models.User:
    """Same as get_current_user, but also accepts the JWT as a `?token=`
    query param. Only meant for the /social/{platform}/login redirect: a
    plain browser navigation to that URL can't carry an Authorization
    header, so the frontend passes the token it already holds in the URL
    instead. Every other endpoint should keep using get_current_user."""
    return await get_current_user(token or bearer_token, db)


def require_role(*roles: models.Role):
    def dependency(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed for this role")
        return user

    return dependency
