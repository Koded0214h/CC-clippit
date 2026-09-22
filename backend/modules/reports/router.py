import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from core.rate_limit import limiter
from modules.audit import service as audit
from modules.auth.deps import get_current_user
from modules.auth.models import Role, User
from modules.uploads.router import owned_upload

from . import models, schemas

router = APIRouter(prefix="/reports", tags=["reports"])
admin_router = APIRouter(prefix="/admin/reports", tags=["admin"])


@router.post("", response_model=schemas.ReportOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def report(
    request: Request, payload: schemas.ReportCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    for upload_id in payload.evidence_upload_ids:
        await owned_upload(db, upload_id, user.id, kinds=("image", "evidence"))
    row = models.Report(
        reporter_id=user.id, target_type=payload.target_type, target_id=payload.target_id,
        reason=payload.reason, details=payload.details, evidence_upload_ids=payload.evidence_upload_ids,
    )
    db.add(row)
    audit.record(db, "report.filed", actor_id=user.id, subject_id=row.id, target_type=payload.target_type.value)
    await db.commit()
    await db.refresh(row)
    return schemas.ReportOut.model_validate(row)


@router.get("/me", response_model=list[schemas.ReportOut])
async def my_reports(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Customer-safe: status only, never the moderation notes."""
    rows = await db.scalars(select(models.Report).where(models.Report.reporter_id == user.id).order_by(models.Report.created_at.desc()))
    return [schemas.ReportOut.model_validate(r) for r in rows]


# --- operator side -------------------------------------------------------------


def _require_admin(user: User) -> None:
    if user.role != Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")


@admin_router.get("", response_model=list[schemas.ReportAdminOut])
async def queue(
    target_type: models.ReportTargetType | None = None,
    status_filter: models.ReportStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    query = select(models.Report)
    if target_type:
        query = query.where(models.Report.target_type == target_type)
    if status_filter:
        query = query.where(models.Report.status == status_filter)
    rows = await db.scalars(query.order_by(models.Report.created_at.desc()).limit(limit).offset(offset))
    return [schemas.ReportAdminOut.model_validate(r) for r in rows]


@admin_router.get("/{report_id}", response_model=schemas.ReportAdminOut)
async def report_detail(report_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _require_admin(user)
    row = await db.get(models.Report, report_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return schemas.ReportAdminOut.model_validate(row)


@admin_router.post("/{report_id}/resolve", response_model=schemas.ReportAdminOut)
async def resolve_report(
    report_id: uuid.UUID, payload: schemas.ReportResolve, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Records the moderation decision. Like disputes, it doesn't itself
    pause a campaign or sanction an account — those are separate,
    already-audited actions through their own admin endpoints."""
    _require_admin(user)
    row = await db.get(models.Report, report_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    if row.status == models.ReportStatus.resolved:
        raise HTTPException(status.HTTP_409_CONFLICT, "This report is already resolved.")
    row.status = models.ReportStatus.resolved
    row.resolution = payload.resolution
    row.resolution_note = payload.note
    row.resolved_by = user.id
    row.resolved_at = datetime.now(timezone.utc)
    audit.record(db, "report.resolved", actor_id=user.id, subject_id=row.id, resolution=payload.resolution.value)
    await db.commit()
    await db.refresh(row)
    return schemas.ReportAdminOut.model_validate(row)
