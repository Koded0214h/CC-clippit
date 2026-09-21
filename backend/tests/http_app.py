"""HTTP tests against the real FastAPI app on a disposable Postgres schema.

Campaigns use ARRAY and native enums, so SQLite cannot host these tests.
They skip if Docker Postgres on 5433 is not reachable.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.database import Base
from core.deps import get_db

import modules.auth.models  # noqa: F401
import modules.campaigns.models  # noqa: F401
import modules.creators.models  # noqa: F401
import modules.intelligence.models  # noqa: F401
import modules.notifications.models  # noqa: F401
import modules.organisations.models  # noqa: F401
import modules.submissions.models  # noqa: F401
import modules.uploads.models  # noqa: F401

TEST_URL = "postgresql+asyncpg://clippit:clippit@localhost:5433/clippit_http_test"


async def _ensure_database() -> bool:
    try:
        admin = create_async_engine(
            "postgresql+asyncpg://clippit:clippit@localhost:5433/clippit",
            isolation_level="AUTOCOMMIT",
        )
    except Exception:
        return False
    try:
        async with admin.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = 'clippit_http_test'")
            )
            if not exists:
                await conn.execute(text("CREATE DATABASE clippit_http_test"))
        return True
    except Exception:
        return False
    finally:
        await admin.dispose()


@pytest_asyncio.fixture
async def api() -> AsyncIterator[httpx.AsyncClient]:
    if not await _ensure_database():
        pytest.skip("Docker Postgres on localhost:5433 is not available")

    engine = create_async_engine(TEST_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    from main import app

    app.dependency_overrides[get_db] = _db
    if hasattr(app.state, "limiter"):
        app.state.limiter.enabled = False

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def latest_code(email: str) -> str:
    """The six-digit code from the newest email sent to `email` (the
    console sender keeps them in memory — see core.email)."""
    import re

    from core.email import get_email_sender

    message = get_email_sender().last_to(email)
    assert message is not None, f"no email was sent to {email}"
    match = re.search(r"\b(\d{6})\b", message.text)
    assert match, message.text
    return match.group(1)


async def signup(client: httpx.AsyncClient, role: str = "creator", *, verify: bool = True) -> tuple[str, dict]:
    """Creates an account and, by default, confirms its email the way a user
    would (read the code, submit it) so tests start from a normal account."""
    email = f"{role}-{uuid.uuid4().hex[:8]}@example.com"
    password = "DemoPassword123!"
    r = await client.post(
        "/auth/signup",
        json={"email": email, "password": password, "full_name": f"Test {role}", "role": role},
    )
    r.raise_for_status()
    body = r.json()
    if verify:
        v = await client.post(
            "/auth/verify-email",
            headers={"Authorization": f"Bearer {body['access_token']}"},
            json={"code": latest_code(email)},
        )
        v.raise_for_status()
        body["user"] = v.json()
    return email, body
