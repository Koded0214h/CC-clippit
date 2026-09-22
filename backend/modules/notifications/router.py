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
    query = select(models.Notification).where(
        models.Notification.user_id == user.id, models.Notification.archived_at.is_(None)
    )
    if unread_only:
        query = query.where(models.Notification.read_at.is_(None))
    if before:
        query = query.where(models.Notification.created_at < before)
    rows = await db.scalars(query.order_by(models.Notification.created_at.desc()).limit(limit))
    return schemas.NotificationList(
        unread_count=await _unread_count(db, user.id), items=[schemas.NotificationOut.from_model(n) for n in rows]
    )


async def _unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count()).select_from(models.Notification).where(
                models.Notification.user_id == user_id,
                models.Notification.read_at.is_(None),
                models.Notification.archived_at.is_(None),
            )
        )
    ) or 0


@router.get("/unread-count", response_model=schemas.UnreadCountOut)
async def unread_count(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """The shell badge — cheap on purpose: no rows, just a count."""
    return schemas.UnreadCountOut(unread_count=await _unread_count(db, user.id))


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


@router.post("/{notification_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_notification(
    notification_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Hides it from the inbox; the row (and the event it was for) stays."""
    note = await db.get(models.Notification, notification_id)
    if note is None or note.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    if note.archived_at is None:
        note.archived_at = datetime.now(timezone.utc)
        await db.commit()


# --- push subscriptions (no /notifications prefix — see push_router below) ----

push_router = APIRouter(prefix="/push-subscriptions", tags=["notifications"])


@push_router.post("", response_model=schemas.PushSubscriptionOut, status_code=status.HTTP_201_CREATED)
async def register_push_subscription(
    payload: schemas.PushSubscriptionIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(select(models.PushSubscription).where(models.PushSubscription.endpoint == payload.endpoint))
    if existing:
        existing.user_id = user.id  # the browser may have re-subscribed as a different account
        existing.p256dh_key = payload.p256dh_key
        existing.auth_key = payload.auth_key
        sub = existing
    else:
        sub = models.PushSubscription(user_id=user.id, **payload.model_dump())
        db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return schemas.PushSubscriptionOut(id=sub.id, endpoint=sub.endpoint, created_at=sub.created_at)


@push_router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_push_subscription(
    subscription_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    sub = await db.get(models.PushSubscription, subscription_id)
    if sub is None or sub.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription not found")
    await db.delete(sub)
    await db.commit()
