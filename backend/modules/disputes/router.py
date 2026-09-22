import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.deps import get_db
from modules.audit import service as audit
from modules.auth.deps import get_current_user
from modules.auth.models import Role, User
from modules.uploads.router import owned_upload

from . import models, schemas, service

router = APIRouter(prefix="/disputes", tags=["disputes"])
admin_router = APIRouter(prefix="/admin/disputes", tags=["admin"])


async def _load_owned(dispute_id: uuid.UUID, user: User, db: AsyncSession) -> models.Dispute:
    dispute = await db.scalar(
        select(models.Dispute).options(selectinload(models.Dispute.messages)).where(models.Dispute.id == dispute_id)
    )
    if dispute is None or (dispute.user_id != user.id and user.role != Role.admin):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dispute not found")
    return dispute


@router.post("", response_model=schemas.DisputeDetailOut, status_code=status.HTTP_201_CREATED)
async def open_dispute(payload: schemas.DisputeCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        dispute = await service.create_dispute(db, user, payload.type, payload.resource_id, payload.reason)
    except service.DisputeError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    audit.record(db, "dispute.opened", actor_id=user.id, subject_id=dispute.id, amount=dispute.amount_at_risk)
    await db.commit()
    dispute = await _load_owned(dispute.id, user, db)
    return await service.detail_out(db, dispute)


@router.get("", response_model=list[schemas.DisputeOut])
async def list_disputes(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(models.Dispute).where(models.Dispute.user_id == user.id).order_by(models.Dispute.updated_at.desc()))
    return [await service.out(db, d) for d in rows]


@router.get("/{dispute_id}", response_model=schemas.DisputeDetailOut)
async def get_dispute(dispute_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    dispute = await _load_owned(dispute_id, user, db)
    if user.role != Role.admin:
        dispute.customer_last_read_at = service.now()
        await db.commit()
        await db.refresh(dispute)
    return await service.detail_out(db, dispute)


@router.post("/{dispute_id}/messages", response_model=schemas.DisputeDetailOut, status_code=status.HTTP_201_CREATED)
async def reply(
    dispute_id: uuid.UUID, payload: schemas.DisputeMessageCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    dispute = await _load_owned(dispute_id, user, db)
    if dispute.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the dispute's opener can reply here")
    if dispute.status in (models.DisputeStatus.resolved, models.DisputeStatus.withdrawn):
        raise HTTPException(status.HTTP_409_CONFLICT, f"This dispute is {dispute.status.value}.")
    for upload_id in payload.evidence_upload_ids:
        await owned_upload(db, upload_id, user.id, kinds=("image", "evidence"))
    db.add(
        models.DisputeMessage(
            dispute_id=dispute.id, author_id=user.id, from_admin=False, body=payload.body,
            evidence_upload_ids=payload.evidence_upload_ids,
        )
    )
    if dispute.status == models.DisputeStatus.awaiting_customer:
        dispute.status = models.DisputeStatus.open
    dispute.customer_last_read_at = service.now()
    await db.commit()
    dispute = await _load_owned(dispute_id, user, db)
    return await service.detail_out(db, dispute)


@router.post("/{dispute_id}/withdraw", response_model=schemas.DisputeOut)
async def withdraw(dispute_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    dispute = await _load_owned(dispute_id, user, db)
    if dispute.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the dispute's opener can withdraw it")
    if dispute.status in (models.DisputeStatus.resolved, models.DisputeStatus.withdrawn):
        raise HTTPException(status.HTTP_409_CONFLICT, f"This dispute is already {dispute.status.value}.")
    dispute.status = models.DisputeStatus.withdrawn
    audit.record(db, "dispute.withdrawn", actor_id=user.id, subject_id=dispute.id)
    await db.commit()
    await db.refresh(dispute)
    return await service.out(db, dispute)


# --- operator side -------------------------------------------------------------


def _require_admin(user: User) -> None:
    if user.role != Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")


async def _load(dispute_id: uuid.UUID, db: AsyncSession) -> models.Dispute:
    dispute = await db.scalar(
        select(models.Dispute).options(selectinload(models.Dispute.messages)).where(models.Dispute.id == dispute_id)
    )
    if dispute is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dispute not found")
    return dispute


@admin_router.get("", response_model=list[schemas.DisputeOut])
async def queue(
    type_filter: models.DisputeType | None = Query(None, alias="type"),
    status_filter: models.DisputeStatus | None = Query(None, alias="status"),
    assignee_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    query = select(models.Dispute)
    if type_filter:
        query = query.where(models.Dispute.type == type_filter)
    if status_filter:
        query = query.where(models.Dispute.status == status_filter)
    if assignee_id:
        query = query.where(models.Dispute.assignee_id == assignee_id)
    rows = await db.scalars(query.order_by(models.Dispute.deadline_at.asc()).limit(limit).offset(offset))
    return [await service.out(db, d) for d in rows]


@admin_router.get("/{dispute_id}", response_model=schemas.DisputeAdminOut)
async def dispute_detail(dispute_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _require_admin(user)
    return await service.admin_out(db, await _load(dispute_id, db))


@admin_router.patch("/{dispute_id}", response_model=schemas.DisputeAdminOut)
async def update_dispute(
    dispute_id: uuid.UUID, payload: schemas.DisputePatch, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    _require_admin(user)
    dispute = await _load(dispute_id, db)
    if dispute.status in (models.DisputeStatus.resolved, models.DisputeStatus.withdrawn):
        raise HTTPException(status.HTTP_409_CONFLICT, f"This dispute is already {dispute.status.value}.")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(dispute, field, value)
    audit.record(db, "dispute.updated", actor_id=user.id, subject_id=dispute.id, fields=sorted(changes))
    await db.commit()
    return await service.admin_out(db, await _load(dispute_id, db))


@admin_router.post("/{dispute_id}/resolve", response_model=schemas.DisputeAdminOut)
async def resolve_dispute(
    dispute_id: uuid.UUID, payload: schemas.DisputeResolve, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Records the decision. It does not itself invoke a refund, a payout
    retry, or a verdict override — those are separate, already-audited
    domain actions the operator takes through their own endpoints. This
    stays a record of *what was decided*, not a trigger for *what to do*,
    so a resolution is never silently coupled to an action that might
    itself fail."""
    _require_admin(user)
    dispute = await _load(dispute_id, db)
    if dispute.status in (models.DisputeStatus.resolved, models.DisputeStatus.withdrawn):
        raise HTTPException(status.HTTP_409_CONFLICT, f"This dispute is already {dispute.status.value}.")
    dispute.status = models.DisputeStatus.resolved
    dispute.resolution = payload.resolution
    dispute.resolution_note = payload.note
    dispute.resolved_by = user.id
    dispute.resolved_at = service.now()
    audit.record(
        db, "dispute.resolved", actor_id=user.id, subject_id=dispute.id, resolution=payload.resolution.value,
    )
    await db.commit()
    return await service.admin_out(db, await _load(dispute_id, db))


@admin_router.post("/{dispute_id}/reopen", response_model=schemas.DisputeAdminOut)
async def reopen_dispute(dispute_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _require_admin(user)
    dispute = await _load(dispute_id, db)
    if dispute.status != models.DisputeStatus.resolved:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a resolved dispute can be reopened.")
    dispute.status = models.DisputeStatus.open
    dispute.deadline_at = service.now() + service.RESOLUTION_SLA
    audit.record(db, "dispute.reopened", actor_id=user.id, subject_id=dispute.id)
    await db.commit()
    return await service.admin_out(db, await _load(dispute_id, db))
