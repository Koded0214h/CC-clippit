import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

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

    user = await db.get(models.User, uuid.UUID(payload["sub"]))
    if not user:
        raise unauthorized
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
