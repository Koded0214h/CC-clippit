"""/observe — password-gated operations dashboard (health, traffic, latency, logs).

Disabled (404) until OBSERVE_PASSWORD is set in the server's .env, so the
route never exists with a guessable default. Login sets a signed, HttpOnly,
SameSite=Strict cookie scoped to /observe.
"""

import hashlib
import hmac
import secrets
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import text

from core.config import get_settings
from core.database import AsyncSessionLocal
from core.rate_limit import limiter

from . import collector

router = APIRouter(prefix="/observe", tags=["observe"])

COOKIE = "observe_session"
SESSION_SECONDS = 12 * 3600
_PAGE = Path(__file__).parent / "static" / "index.html"


def _enabled() -> bool:
    return bool(get_settings().observe_password)


def _sign(payload: str) -> str:
    key = f"observe:{get_settings().jwt_secret}".encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def _make_token() -> str:
    expires = str(int(time.time()) + SESSION_SECONDS)
    return f"{expires}.{_sign(expires)}"


def _valid_token(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    expires, sig = token.split(".", 1)
    if not expires.isdigit() or int(expires) < time.time():
        return False
    return hmac.compare_digest(sig, _sign(expires))


def _require_session(request: Request) -> None:
    if not _enabled():
        raise HTTPException(404)
    if not _valid_token(request.cookies.get(COOKIE)):
        raise HTTPException(401, "Not signed in")


class LoginBody(BaseModel):
    username: str
    password: str


@router.get("", include_in_schema=False)
@router.get("/", include_in_schema=False)
def page() -> HTMLResponse:
    if not _enabled():
        raise HTTPException(404)
    return HTMLResponse(
        _PAGE.read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"},
    )


@router.post("/api/login")
@limiter.limit("5/minute")
def login(request: Request, response: Response, body: LoginBody):
    if not _enabled():
        raise HTTPException(404)
    s = get_settings()
    # Both compared unconditionally so timing doesn't reveal which was wrong.
    user_ok = secrets.compare_digest(body.username.encode(), s.observe_username.encode())
    pass_ok = secrets.compare_digest(body.password.encode(), s.observe_password.encode())
    if not (user_ok and pass_ok):
        raise HTTPException(401, "Wrong username or password")
    response.set_cookie(
        COOKIE, _make_token(), max_age=SESSION_SECONDS, httponly=True,
        secure=s.environment == "production", samesite="strict", path="/observe",
    )
    return {"ok": True}


@router.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/observe")
    return {"ok": True}


async def _probe_db() -> dict:
    started = time.perf_counter()
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        ms = (time.perf_counter() - started) * 1000
        collector.record_db_probe(True, ms)
        return {"ok": True, "ms": round(ms, 1), "error": None}
    except Exception as exc:  # noqa: BLE001 — the point is to report, not raise
        collector.record_db_probe(False, None, type(exc).__name__)
        return {"ok": False, "ms": None, "error": type(exc).__name__}


@router.get("/api/summary")
async def summary(request: Request, window: int = 30):
    _require_session(request)
    s = get_settings()
    db = await _probe_db()
    data = collector.snapshot(window)
    data["health"] = {
        # Liveness: this handler ran, so the process and event loop are alive.
        "liveness": {"ok": True},
        # Readiness: can it actually serve traffic (needs the database).
        "readiness": {"ok": db["ok"]},
        "database": db,
    }
    data["environment"] = s.environment
    data["jobs_enabled"] = s.background_jobs_enabled
    return data


@router.get("/api/logs")
def logs(request: Request, after: int = 0, limit: int = 500):
    _require_session(request)
    rows = collector.logs_since(max(after, 0), max(1, min(limit, 1000)))
    return {"logs": rows, "latest": rows[-1]["id"] if rows else after}
