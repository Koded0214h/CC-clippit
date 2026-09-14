"""Pytest bootstrap for the whole backend.

Its presence at the repo root is what puts `backend/` on `sys.path`, so
tests can `from core.platforms import ...` the same way the app does.

It also pins the database URL *before* anything imports `core.database`,
which builds an engine at import time. Two reasons: the suite can then run
with no Postgres and no `asyncpg` installed, and there is no configuration
mistake that could point a test run at a real database.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
