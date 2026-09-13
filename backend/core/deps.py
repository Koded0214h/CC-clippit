from collections.abc import AsyncGenerator

from fastapi import Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .database import AsyncSessionLocal

settings = get_settings()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def require_internal_secret(x_internal_secret: str = Header(default="")) -> None:
    """Guards internal-only routes meant for other modules/services, not a
    browser — checked with a shared secret rather than a user's JWT."""
    if x_internal_secret != settings.internal_service_secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal service secret")
