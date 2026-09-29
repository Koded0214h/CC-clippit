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
# Password hashing at production cost would dominate the suite's runtime.
os.environ.setdefault("BCRYPT_ROUNDS", "4")
# Same reasoning as DATABASE_URL above: a real .env (SMTP/Cloudinary
# credentials for local dev) must never let a test run send a real email
# or upload to a real storage account.
os.environ.setdefault("EMAIL_BACKEND", "console")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("PAYMENT_PROVIDER", "sandbox")
# Tests exercise the "default secret" checks (core/startup.py), so a real
# .env's generated secrets must not replace the dev defaults here.
for _name in ("JWT_SECRET", "INTERNAL_SERVICE_SECRET", "PAYMENT_WEBHOOK_SECRET"):
    os.environ.setdefault(_name, "dev-only-not-secret")
# Same again for every OAuth provider: several tests assert a provider is
# "unavailable" with no credentials configured (e.g. Google sign-in), which
# a real .env's live client id/secret would otherwise silently contradict.
for _name in (
    "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
    "TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET",
    "FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET",
    "INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET",
    "THREADS_APP_ID", "THREADS_APP_SECRET",
    "X_CLIENT_ID", "X_CLIENT_SECRET", "TWITTERAPI_IO_KEY",
    "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_API_KEY",
):
    os.environ.setdefault(_name, "")
