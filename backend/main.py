"""Clippit backend — single monolithic FastAPI app.

Every module (auth today; campaigns, submissions, payouts, admin as they
land) mounts its routers here. Run from the backend/ directory:

    uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.database import init_db
from modules.auth.internal_router import router as auth_internal_router
from modules.auth.router import router as auth_router
from modules.auth.social_router import router as auth_social_router

settings = get_settings()

app = FastAPI(title="Clippit API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.frontend_origin.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Auth & Accounts (Koded) ---
app.include_router(auth_router)
app.include_router(auth_social_router)
app.include_router(auth_internal_router)

# --- Campaign Management, Funding, Content Submission, Admin (Adam) ---
# app.include_router(campaigns_router)
# ...

# --- Intelligence Engine, Payout Service (Koded) ---
# app.include_router(engine_router)
# app.include_router(payouts_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
