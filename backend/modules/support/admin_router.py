import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.deps import get_db
from modules.audit import service as audit
from modules.auth.deps import get_current_user
from modules.auth.models import Role, User

from . import models, schemas, service

router = APIRouter(prefix="/admin/support/tickets", tags=["admin"])


def _require_admin(user: User) -> None:
    if user.role != Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")


async def _load(ticket_id: uuid.UUID, db: AsyncSession) -> models.SupportTicket:
    ticket = await db.scalar(
        select(models.SupportTicket)
        .options(selectinload(models.SupportTicket.messages))
        .where(models.SupportTicket.id == ticket_id)
        .execution_options(populate_existing=True)
    )
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    return ticket


async def _notes(db: AsyncSession, ticket_id: uuid.UUID) -> list[models.SupportNote]:
    return list(
        await db.scalars(
            select(models.SupportNote).where(models.SupportNote.ticket_id == ticket_id).order_by(models.SupportNote.created_at)
        )
    )


@router.get("", response_model=list[schemas.TicketOut])
async def queue(
    status_filter: models.TicketStatus | None = Query(None, alias="status"),
    category: str | None = None,
    assignee_id: uuid.UUID | None = None,
    priority: models.TicketPriority | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    query = select(models.SupportTicket)
    if status_filter:
        query = query.where(models.SupportTicket.status == status_filter)
    if category:
        query = query.where(models.SupportTicket.category == category)
    if assignee_id:
        query = query.where(models.SupportTicket.assignee_id == assignee_id)
    if priority:
        query = query.where(models.SupportTicket.priority == priority)
    rows = await db.scalars(query.order_by(models.SupportTicket.updated_at.desc()).limit(limit).offset(offset))
    return [await service.ticket_out(db, t) for t in rows]


@router.get("/{ticket_id}", response_model=schemas.TicketAdminOut)
async def ticket_detail(ticket_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _require_admin(user)
    ticket = await _load(ticket_id, db)
    return await service.admin_out(db, ticket, await _notes(db, ticket_id))


@router.post("/{ticket_id}/messages", response_model=schemas.TicketAdminOut, status_code=status.HTTP_201_CREATED)
async def operator_reply(
    ticket_id: uuid.UUID, payload: schemas.MessageCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    _require_admin(user)
    ticket = await _load(ticket_id, db)
    db.add(models.SupportMessage(ticket_id=ticket.id, author_id=user.id, from_admin=True, body=payload.body))
    await db.commit()
    ticket = await _load(ticket_id, db)
    return await service.admin_out(db, ticket, await _notes(db, ticket_id))


@router.patch("/{ticket_id}", response_model=schemas.TicketAdminOut)
async def update_ticket(
    ticket_id: uuid.UUID, payload: schemas.TicketPatch, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    _require_admin(user)
    ticket = await _load(ticket_id, db)
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] == models.TicketStatus.closed and ticket.status != models.TicketStatus.closed:
        ticket.closed_at = service.now()
    elif "status" in changes and changes["status"] == models.TicketStatus.open:
        ticket.closed_at = None
    for field, value in changes.items():
        setattr(ticket, field, value)
    audit.record(db, "support.ticket_updated", actor_id=user.id, subject_id=ticket.id, fields=sorted(changes))
    await db.commit()
    ticket = await _load(ticket_id, db)
    return await service.admin_out(db, ticket, await _notes(db, ticket_id))


@router.post("/{ticket_id}/notes", response_model=schemas.NoteOut, status_code=status.HTTP_201_CREATED)
async def add_note(
    ticket_id: uuid.UUID, payload: schemas.NoteCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    _require_admin(user)
    await _load(ticket_id, db)  # 404s if the ticket doesn't exist
    note = models.SupportNote(ticket_id=ticket_id, author_id=user.id, body=payload.body)
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return schemas.NoteOut.model_validate(note)
