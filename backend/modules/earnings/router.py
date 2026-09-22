import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from modules.auth.deps import get_current_user
from modules.auth.models import Role, User

from . import models, queries, schemas

router = APIRouter(tags=["earnings"])


def _creator_only(user: User) -> None:
    if user.role != Role.creator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a creator account has earnings")


@router.get("/earnings/summary", response_model=schemas.EarningsSummary)
async def earnings_summary(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Payable / in hold / paid — the Earnings screen and the dashboard's
    money card."""
    _creator_only(user)
    return await queries.summary(db, user.id)


@router.get("/earnings/history", response_model=schemas.EarningsHistory)
async def earnings_history(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _creator_only(user)
    return await queries.history(db, user.id, limit, offset)


@router.get("/earnings/entries/{entry_id}", response_model=schemas.EarningEntryDetail)
async def earning_entry_detail(
    entry_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """"Every naira traces to a platform snapshot" — the full provenance
    behind one accrual on the earnings history list."""
    detail = await queries.entry_detail(db, entry_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    owner_row = await db.get(models.EarningEntry, entry_id)
    if user.role != Role.admin and (owner_row is None or owner_row.creator_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    return detail


@router.get("/leaderboard", response_model=schemas.Leaderboard)
async def leaderboard(
    period: Literal["week", "all"] = "week",
    campaign_id: uuid.UUID | None = None,
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Creators ranked by verified views. Any signed-in user may read it."""
    return await queries.leaderboard(db, user.id, period=period, campaign_id=campaign_id, limit=limit)
