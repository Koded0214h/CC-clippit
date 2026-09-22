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
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.bcrypt_rounds)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: uuid.UUID, role: str, session_id: uuid.UUID | None = None) -> str:
    """Every token gets a unique `jti` so a single token — not every token
    this user holds — can be revoked on logout (see modules.auth.models.RevokedToken).
    `session_id` (claim `sid`) is what lets `DELETE /auth/sessions/{id}`
    revoke a whole device immediately rather than waiting out the token's
    natural expiry — see modules.auth.models.Session. It's optional only
    because a few internal/legacy call sites don't have a session yet."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "role": role, "jti": str(uuid.uuid4()), "iat": now, "exp": expire}
    if session_id is not None:
        payload["sid"] = str(session_id)
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


def create_google_state_token(*, nonce: str, intent: str, role: str | None, link_user_id: uuid.UUID | None) -> str:
    """Same reasoning as `create_oauth_state_token`: the round trip through
    Google is stateless, so everything the callback needs — including the
    nonce it must see echoed back in the id_token — travels signed in
    `state` rather than in a server-side session.
    `intent` is "login" (sign in or create an account) or "link" (attach
    Google to the already-signed-in `link_user_id`)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload = {
        "nonce": nonce,
        "intent": intent,
        "role": role,
        "link_user_id": str(link_user_id) if link_user_id else None,
        "purpose": "google_oauth_state",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_google_state_token(token: str) -> dict | None:
    payload = decode_access_token(token)
    if not payload or payload.get("purpose") != "google_oauth_state":
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


# --- refresh tokens ----------------------------------------------------------
# The bearer value returned to a client is "<row id>.<secret>"; only the
# secret's hash is ever stored (see modules.auth.models.RefreshToken).


def new_refresh_secret() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_secret(secret: str) -> str:
    return hashlib.sha256(f"{settings.jwt_secret}:{secret}".encode()).hexdigest()


def refresh_secret_matches(secret: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_refresh_secret(secret), expected_hash)


def parse_refresh_token(token: str) -> tuple[uuid.UUID, str] | None:
    token_id, _, secret = token.partition(".")
    if not secret:
        return None
    try:
        return uuid.UUID(token_id), secret
    except ValueError:
        return None
