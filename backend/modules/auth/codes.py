"""One-time codes: issue, throttle, check.

Rules, all enforced here so no route can forget one:

- A code is six digits, stored only as an HMAC (see `core.security.hash_code`).
- One live code per (user, purpose); asking for another replaces it.
- A new code can't be requested inside the cooldown window — the caller is
  told how long to wait, which is what the "Send a new code" button counts down.
- A code expires after `otp_ttl_minutes`.
- Five wrong guesses burn the code; the user has to ask for a new one.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.security import codes_match, generate_otp, hash_code

from . import models


class CodeError(Exception):
    """Base for every reason a code can't be used. `message` is user-safe."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CooldownActive(CodeError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Wait {retry_after}s before asking for another code.")
        self.retry_after = retry_after


class CodeInvalid(CodeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def issue_code(db: AsyncSession, user: models.User, purpose: models.AuthCodePurpose) -> str:
    """Create (replacing any live one) and return the plaintext code. The
    caller emails it; the plaintext is never stored."""
    settings = get_settings()
    existing = await db.scalar(
        select(models.AuthCode).where(models.AuthCode.user_id == user.id, models.AuthCode.purpose == purpose)
    )
    if existing:
        elapsed = (_now() - existing.created_at).total_seconds()
        if elapsed < settings.otp_resend_cooldown_seconds:
            raise CooldownActive(int(settings.otp_resend_cooldown_seconds - elapsed) + 1)
        await db.execute(delete(models.AuthCode).where(models.AuthCode.id == existing.id))
        await db.flush()

    code = generate_otp()
    db.add(
        models.AuthCode(
            user_id=user.id,
            purpose=purpose,
            code_hash=hash_code(user.id, purpose.value, code),
            expires_at=_now() + timedelta(minutes=settings.otp_ttl_minutes),
        )
    )
    await db.flush()
    return code


async def check_code(db: AsyncSession, user: models.User, purpose: models.AuthCodePurpose, code: str) -> None:
    """Consume the code if it is right. Raises `CodeInvalid` otherwise, with
    the same message for wrong / expired / missing — the response must not
    tell an attacker which of those it was."""
    settings = get_settings()
    generic = CodeInvalid("That code isn't right or has expired. Ask for a new one.")

    row = await db.scalar(
        select(models.AuthCode).where(models.AuthCode.user_id == user.id, models.AuthCode.purpose == purpose)
    )
    if row is None or row.expires_at < _now():
        raise generic

    if not codes_match(row.code_hash, user.id, purpose.value, code):
        row.attempts += 1
        if row.attempts >= settings.otp_max_attempts:
            await db.delete(row)
        await db.commit()
        raise generic

    await db.delete(row)
    await db.flush()
