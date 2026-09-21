import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from modules.auth.deps import get_current_user
from modules.auth.models import User

from . import models, schemas

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=schemas.NotificationList)
async def list_notifications(
    unread_only: bool = False,
    limit: int = Query(30, ge=1, le=100),
    before: datetime | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Newest first. Page backwards with `before=<created_at of the last item>`."""
    query = select(models.Notification).where(models.Notification.user_id == user.id)
    if unread_only:
        query = query.where(models.Notification.read_at.is_(None))
    if before:
        query = query.where(models.Notification.created_at < before)
    rows = await db.scalars(query.order_by(models.Notification.created_at.desc()).limit(limit))
    unread = await db.scalar(
        select(func.count()).select_from(models.Notification).where(
            models.Notification.user_id == user.id, models.Notification.read_at.is_(None)
        )
    )
    return schemas.NotificationList(
        unread_count=unread or 0, items=[schemas.NotificationOut.from_model(n) for n in rows]
    )


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(
        update(models.Notification)
        .where(models.Notification.user_id == user.id, models.Notification.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    await db.commit()


@router.post("/{notification_id}/read", response_model=schemas.NotificationOut)
async def mark_read(
    notification_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    note = await db.get(models.Notification, notification_id)
    if note is None or note.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    if note.read_at is None:
        note.read_at = datetime.now(timezone.utc)
        await db.commit()
    return schemas.NotificationOut.from_model(note)
