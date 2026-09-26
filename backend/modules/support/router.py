"""Customer-facing support tickets. See `admin_router` for the operator
side (queue, assignment, internal notes)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.deps import get_db
from modules.auth.deps import get_current_user
from modules.auth.models import Role, User
from modules.uploads.router import owned_upload

from . import models, schemas, service

router = APIRouter(prefix="/support", tags=["support"])


async def _load_owned(ticket_id: uuid.UUID, user: User, db: AsyncSession) -> models.SupportTicket:
    ticket = await db.scalar(
        select(models.SupportTicket)
        .options(selectinload(models.SupportTicket.messages))
        .where(models.SupportTicket.id == ticket_id)
        # The session doesn't expire on commit, so without this a reload after
        # adding a message returns the cached, pre-reply message list.
        .execution_options(populate_existing=True)
    )
    if ticket is None or (ticket.user_id != user.id and user.role != Role.admin):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    return ticket


async def _check_attachments(db: AsyncSession, ids: list[uuid.UUID], owner_id: uuid.UUID) -> None:
    for upload_id in ids:
        await owned_upload(db, upload_id, owner_id, kinds=("image", "evidence"))


@router.post("/tickets", response_model=schemas.TicketDetailOut, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: schemas.TicketCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await _check_attachments(db, payload.attachment_upload_ids, user.id)
    ticket = models.SupportTicket(
        user_id=user.id, category=payload.category, subject=payload.subject,
        resource_type=payload.resource_type, resource_id=payload.resource_id,
    )
    db.add(ticket)
    await db.flush()
    db.add(
        models.SupportMessage(
            ticket_id=ticket.id, author_id=user.id, from_admin=False, body=payload.message,
            attachment_upload_ids=payload.attachment_upload_ids,
        )
    )
    await db.commit()
    await db.refresh(ticket)
    ticket = await _load_owned(ticket.id, user, db)
    return await service.ticket_detail_out(db, ticket)


@router.get("/tickets", response_model=list[schemas.TicketOut])
async def list_tickets(
    status_filter: models.TicketStatus | None = Query(None, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(models.SupportTicket).where(models.SupportTicket.user_id == user.id)
    if status_filter:
        query = query.where(models.SupportTicket.status == status_filter)
    rows = await db.scalars(query.order_by(models.SupportTicket.updated_at.desc()))
    return [await service.ticket_out(db, t) for t in rows]


@router.get("/tickets/{ticket_id}", response_model=schemas.TicketDetailOut)
async def get_ticket(ticket_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ticket = await _load_owned(ticket_id, user, db)
    if user.role != Role.admin:
        ticket.customer_last_read_at = service.now()
        await db.commit()
        await db.refresh(ticket)
    return await service.ticket_detail_out(db, ticket)


@router.post("/tickets/{ticket_id}/messages", response_model=schemas.TicketDetailOut, status_code=status.HTTP_201_CREATED)
async def reply(
    ticket_id: uuid.UUID,
    payload: schemas.MessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ticket = await _load_owned(ticket_id, user, db)
    if ticket.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the ticket's owner can reply here")
    await _check_attachments(db, payload.attachment_upload_ids, user.id)
    db.add(
        models.SupportMessage(
            ticket_id=ticket.id, author_id=user.id, from_admin=False, body=payload.body,
            attachment_upload_ids=payload.attachment_upload_ids,
        )
    )
    if ticket.status == models.TicketStatus.closed:
        ticket.status = models.TicketStatus.open
        ticket.closed_at = None
    ticket.customer_last_read_at = service.now()
    await db.commit()
    ticket = await _load_owned(ticket_id, user, db)
    return await service.ticket_detail_out(db, ticket)


@router.post("/tickets/{ticket_id}/close", response_model=schemas.TicketOut)
async def close_ticket(ticket_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ticket = await _load_owned(ticket_id, user, db)
    if ticket.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the ticket's owner can close it")
    if ticket.status != models.TicketStatus.closed:
        ticket.status = models.TicketStatus.closed
        ticket.closed_at = service.now()
        await db.commit()
        await db.refresh(ticket)
    return await service.ticket_out(db, ticket)


@router.post("/tickets/{ticket_id}/reopen", response_model=schemas.TicketOut)
async def reopen_ticket(ticket_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ticket = await _load_owned(ticket_id, user, db)
    if ticket.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the ticket's owner can reopen it")
    if not service.can_reopen(ticket):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This ticket closed too long ago to reopen — open a new one and reference it if it's related.",
        )
    ticket.status = models.TicketStatus.open
    ticket.closed_at = None
    await db.commit()
    await db.refresh(ticket)
    return await service.ticket_out(db, ticket)
