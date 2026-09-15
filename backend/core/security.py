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
    payload = {"sub": str(user_id), "role": role, "jti": str(uuid.uuid4()), "exp": expire}
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
