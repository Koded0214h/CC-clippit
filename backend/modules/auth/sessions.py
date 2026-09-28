"""Sessions and refresh-token rotation — the mechanics behind
`GET/DELETE /auth/sessions*` and `POST /auth/refresh`.

A `Session` is the durable, revocable thing ("this device"); an access
token is a short-lived, unrevocable-until-expiry credential minted from
one. `RefreshToken` rows are the rotation chain that keeps a session
alive without ever handing the client a long-lived access token.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession as DBSession

from core.security import (
    create_access_token,
    hash_refresh_secret,
    new_refresh_secret,
    parse_refresh_token,
    refresh_secret_matches,
)

from . import models

REFRESH_TOKEN_DAYS = 30
REMEMBERED_REFRESH_TOKEN_DAYS = 365


def _device_label(request: Request | None) -> str | None:
    """Best-effort, human-readable device label from the User-Agent —
    never parsed for anything security-relevant, only shown back to the
    person on their own sessions list."""
    if request is None:
        return None
    ua = request.headers.get("user-agent")
    if not ua:
        return None
    return ua[:120]


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    return request.client.host if request.client else None


@dataclass
class IssuedTokens:
    access_token: str
    refresh_token: str
    session: models.Session


async def start_session(db: DBSession, user: models.User, request: Request | None = None) -> IssuedTokens:
    """Login/signup/Google sign-in all funnel through here: one new
    `Session` plus its first `RefreshToken`."""
    session = models.Session(user_id=user.id, device_label=_device_label(request), ip_address=_client_ip(request))
    db.add(session)
    await db.flush()
    access_token = create_access_token(user.id, user.role.value, session_id=session.id)
    refresh_token = await _issue_refresh_token(db, session)
    return IssuedTokens(access_token=access_token, refresh_token=refresh_token, session=session)


async def _issue_refresh_token(db: DBSession, session: models.Session) -> str:
    secret = new_refresh_secret()
    lifetime = REMEMBERED_REFRESH_TOKEN_DAYS if session.remembered_at is not None else REFRESH_TOKEN_DAYS
    row = models.RefreshToken(
        session_id=session.id,
        secret_hash=hash_refresh_secret(secret),
        expires_at=datetime.now(timezone.utc) + timedelta(days=lifetime),
    )
    db.add(row)
    await db.flush()
    return f"{row.id}.{secret}"


class RefreshError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


async def rotate(db: DBSession, refresh_token: str) -> IssuedTokens:
    """Consumes one refresh token and issues the next. A token presented
    twice — already `used_at` — is reuse: the whole session is revoked,
    on the theory that a legitimate client never does that; only someone
    replaying a stolen token would."""
    parsed = parse_refresh_token(refresh_token)
    invalid = RefreshError("This session is no longer valid. Sign in again.")
    if parsed is None:
        raise invalid
    token_id, secret = parsed
    row = await db.get(models.RefreshToken, token_id)
    if row is None or not refresh_secret_matches(secret, row.secret_hash):
        raise invalid

    session = await db.get(models.Session, row.session_id)
    if session is None or session.revoked_at is not None:
        raise invalid

    now = datetime.now(timezone.utc)
    if row.used_at is not None:
        session.revoked_at = now
        raise RefreshError("This session was used from two places at once and has been signed out for safety.")
    if row.expires_at < now:
        raise invalid

    user = await db.get(models.User, session.user_id)
    if user is None or user.deleted_at is not None:
        raise invalid

    row.used_at = now
    session.last_seen_at = now
    new_token = await _issue_refresh_token(db, session)
    new_id = uuid.UUID(new_token.split(".", 1)[0])
    row.replaced_by_id = new_id
    access_token = create_access_token(user.id, user.role.value, session_id=session.id)
    return IssuedTokens(access_token=access_token, refresh_token=new_token, session=session)


async def remember_session(
    db: DBSession, user_id: uuid.UUID, session_id: uuid.UUID
) -> models.Session | None:
    """Marks one verified browser session as persistent.

    Existing, unused refresh credentials for the session are extended too,
    so the token issued by the login that started the verification flow can
    be promoted by the client without being replaced or exposed again.
    """
    session = await db.get(models.Session, session_id)
    if session is None or session.user_id != user_id or session.revoked_at is not None:
        return None

    now = datetime.now(timezone.utc)
    session.remembered_at = now
    await db.execute(
        update(models.RefreshToken)
        .where(
            models.RefreshToken.session_id == session.id,
            models.RefreshToken.used_at.is_(None),
        )
        .values(expires_at=now + timedelta(days=REMEMBERED_REFRESH_TOKEN_DAYS))
    )
    return session


async def list_sessions(db: DBSession, user_id: uuid.UUID) -> list[models.Session]:
    rows = await db.scalars(
        select(models.Session)
        .where(models.Session.user_id == user_id, models.Session.revoked_at.is_(None))
        .order_by(models.Session.last_seen_at.desc())
    )
    return list(rows)


async def revoke_session(db: DBSession, user_id: uuid.UUID, session_id: uuid.UUID) -> models.Session | None:
    session = await db.get(models.Session, session_id)
    if session is None or session.user_id != user_id:
        return None
    session.revoked_at = datetime.now(timezone.utc)
    return session


async def revoke_other_sessions(db: DBSession, user_id: uuid.UUID, keep_session_id: uuid.UUID | None) -> int:
    sessions = await list_sessions(db, user_id)
    now = datetime.now(timezone.utc)
    count = 0
    for session in sessions:
        if session.id == keep_session_id:
            continue
        session.revoked_at = now
        count += 1
    return count
