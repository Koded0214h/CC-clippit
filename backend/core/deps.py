from collections.abc import Generator

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from .config import get_settings
from .database import SessionLocal

settings = get_settings()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_internal_secret(x_internal_secret: str = Header(default="")) -> None:
    """Guards internal-only routes meant for other modules/services, not a
    browser — checked with a shared secret rather than a user's JWT."""
    if x_internal_secret != settings.internal_service_secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal service secret")
