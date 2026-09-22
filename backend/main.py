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
from core.jobs import lifespan
from core.rate_limit import limiter
from modules.admin.router import router as admin_router
from modules.auth.internal_router import router as auth_internal_router
from modules.auth.profile_router import router as auth_profile_router
from modules.auth.google_router import router as auth_google_router
from modules.auth.router import router as auth_router
from modules.auth.social_router import router as auth_social_router
from modules.campaigns.brand_router import router as brand_router
from modules.campaigns.router import router as campaigns_router
from modules.creators.router import router as creators_router
from modules.earnings.router import router as earnings_router
from modules.funding.router import router as funding_router
from modules.intelligence.internal_router import router as intelligence_internal_router
from modules.legal.router import router as legal_router
from modules.notifications.router import router as notifications_router
from modules.organisations.router import router as organisations_router
from modules.payments.router import router as payments_router
from modules.payouts.router import router as payouts_router
from modules.product.router import router as product_router
from modules.reviews.router import router as reviews_router
from modules.submissions.router import router as submissions_router
from modules.uploads.router import media_router, router as uploads_router

import modules.scheduled  # noqa: F401  (registers the periodic jobs)

settings = get_settings()

app = FastAPI(title="Clippit API", version="0.1.0", lifespan=lifespan)

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
app.include_router(auth_google_router)
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
app.include_router(funding_router)
app.include_router(brand_router)
app.include_router(payments_router)
app.include_router(payouts_router)
app.include_router(earnings_router)
app.include_router(reviews_router)
app.include_router(admin_router)
app.include_router(submissions_router)
app.include_router(creators_router)
app.include_router(organisations_router)
app.include_router(uploads_router)
app.include_router(notifications_router)
app.include_router(media_router)
app.include_router(product_router)
app.include_router(legal_router)


@app.get("/health")
def health():
    return {"status": "ok"}
