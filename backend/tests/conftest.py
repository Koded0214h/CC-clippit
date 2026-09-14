"""Shared test fixtures.

The `db` fixture is a fresh in-memory SQLite database per test. The
intelligence models are written to be dialect-portable precisely so this
works (see the docstring in `modules/intelligence/models.py`) — it means
Stage 2's guarantees can be re-checked in a second, by anyone, with no
services running. It does not replace a run against real Postgres before
this ships.
"""

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from core.database import Base
from modules.intelligence import models

#: Only this module's tables. Auth's models use Postgres-only column types
#: and aren't under test here, so creating everything on Base would break
#: the moment someone imports them.
INTELLIGENCE_TABLES = [models.SocialContent.__table__, models.MetricSnapshot.__table__]


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    # StaticPool keeps every checkout on the same connection — without it,
    # ":memory:" hands each connection its own empty database.
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=INTELLIGENCE_TABLES)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()
