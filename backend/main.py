"""Clippit backend — single monolithic FastAPI app.

Every module (auth today; campaigns, submissions, payouts, admin as they
land) mounts its routers here. Run from the backend/ directory:

    alembic upgrade head          # schema is managed by migrations now
    uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.config import get_settings
from core.rate_limit import limiter
from modules.auth.internal_router import router as auth_internal_router
from modules.auth.profile_router import router as auth_profile_router
from modules.auth.router import router as auth_router
from modules.auth.social_router import router as auth_social_router
from modules.campaigns.router import router as campaigns_router
from modules.creators.router import router as creators_router
from modules.intelligence.internal_router import router as intelligence_internal_router
from modules.submissions.router import router as submissions_router

settings = get_settings()

app = FastAPI(title="Clippit API", version="0.1.0")

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.frontend_origin.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": f"Too many requests: {exc.detail}"})


# --- Auth & Accounts (Koded) ---
app.include_router(auth_router)
app.include_router(auth_social_router)
app.include_router(auth_profile_router)
app.include_router(auth_internal_router)

# --- Performance & Trust Intelligence (Adam) ---
# Internal-only: called by Campaign Management / earnings, never a browser.
# See ../architecture/intelligence-contracts.md. (Note the ownership split
# here supersedes backend-modules.md — decision D1.)
app.include_router(intelligence_internal_router)

# --- Campaign Management, Content Submission, Payouts, Admin (Koded) ---
app.include_router(campaigns_router)
app.include_router(submissions_router)
app.include_router(creators_router)
# app.include_router(payouts_router)


@app.get("/health")
def health():
    return {"status": "ok"}
