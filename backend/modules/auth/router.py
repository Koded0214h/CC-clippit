from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from core.rate_limit import limiter
from core.security import create_access_token, decode_access_token, hash_password, verify_password

from . import models, schemas
from .deps import get_current_user, oauth2_scheme

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def signup(request: Request, payload: schemas.SignupRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(models.User).where(models.User.email == payload.email))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")

    user = models.User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(user)
    await db.flush()  # assigns user.id (client-side default) without committing yet
    db.add(models.UserPreferences(user_id=user.id))
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.role.value)
    return schemas.TokenResponse(access_token=token, user=schemas.UserOut.model_validate(user))


@router.post("/login", response_model=schemas.TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, payload: schemas.LoginRequest, db: AsyncSession = Depends(get_db)):
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    user = await db.scalar(select(models.User).where(models.User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise invalid

    token = create_access_token(user.id, user.role.value)
    return schemas.TokenResponse(access_token=token, user=schemas.UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user: models.User = Depends(get_current_user),
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Revokes only the token used to call this endpoint — every other
    token this user holds (another device, another tab) stays valid. See
    modules.auth.models.RevokedToken."""
    payload = decode_access_token(token) if token else None
    jti = payload.get("jti") if payload else None
    if jti and not await db.get(models.RevokedToken, jti):
        db.add(
            models.RevokedToken(
                jti=jti,
                expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            )
        )
        await db.commit()


@router.get("/me", response_model=schemas.UserOut)
async def me(user: models.User = Depends(get_current_user)):
    return schemas.UserOut.model_validate(user)
