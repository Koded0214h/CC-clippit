import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from jwt import PyJWTError as JWTError
from passlib.context import CryptContext

from .config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    """Every token gets a unique `jti` so a single token — not every token
    this user holds — can be revoked on logout (see modules.auth.models.RevokedToken)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "role": role, "jti": str(uuid.uuid4()), "iat": now, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def create_oauth_state_token(user_id: uuid.UUID, provider: str, code_verifier: str | None = None) -> str:
    """A short-lived, signed token carrying who's connecting what — replaces a
    server-side session so the OAuth redirect round trip stays stateless."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload = {
        "sub": str(user_id),
        "provider": provider,
        "code_verifier": code_verifier,
        "purpose": "oauth_state",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_oauth_state_token(token: str) -> dict | None:
    payload = decode_access_token(token)
    if not payload or payload.get("purpose") != "oauth_state":
        return None
    return payload


def generate_otp(length: int = 6) -> str:
    """A uniformly random numeric code (leading zeros allowed)."""
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def hash_code(user_id: uuid.UUID, purpose: str, code: str) -> str:
    """HMAC, bound to the user and purpose, so a code for one flow can't be
    replayed into another and the table alone reveals no live code."""
    message = f"{user_id}:{purpose}:{code}".encode()
    return hmac.new(settings.jwt_secret.encode(), message, hashlib.sha256).hexdigest()


def codes_match(expected_hash: str, user_id: uuid.UUID, purpose: str, code: str) -> bool:
    return hmac.compare_digest(expected_hash, hash_code(user_id, purpose, code))


def create_purpose_token(user_id: uuid.UUID, purpose: str, minutes: int) -> str:
    """A short-lived signed token that authorises exactly one thing (for
    example, setting a new password after a recovery code was accepted)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": str(user_id), "purpose": purpose, "jti": str(uuid.uuid4()), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_purpose_token(token: str, purpose: str) -> dict | None:
    payload = decode_access_token(token)
    if not payload or payload.get("purpose") != purpose:
        return None
    return payload
