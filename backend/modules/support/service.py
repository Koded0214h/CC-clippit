from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.auth.models import User

from . import models, schemas

REOPEN_WINDOW = timedelta(days=14)


def now() -> datetime:
    return datetime.now(timezone.utc)


async def unread_count(db: AsyncSession, ticket: models.SupportTicket) -> int:
    return (
        await db.scalar(
            select(func.count()).select_from(models.SupportMessage).where(
                models.SupportMessage.ticket_id == ticket.id,
                models.SupportMessage.from_admin.is_(True),
                models.SupportMessage.created_at > ticket.customer_last_read_at,
            )
        )
    ) or 0


async def ticket_out(db: AsyncSession, ticket: models.SupportTicket) -> schemas.TicketOut:
    return schemas.TicketOut(
        id=ticket.id, category=ticket.category, subject=ticket.subject, status=ticket.status,
        priority=ticket.priority, resource_type=ticket.resource_type, resource_id=ticket.resource_id,
        unread_count=await unread_count(db, ticket), created_at=ticket.created_at, updated_at=ticket.updated_at,
        closed_at=ticket.closed_at,
    )


async def ticket_detail_out(db: AsyncSession, ticket: models.SupportTicket) -> schemas.TicketDetailOut:
    base = await ticket_out(db, ticket)
    return schemas.TicketDetailOut(**base.model_dump(), messages=[schemas.MessageOut.model_validate(m) for m in ticket.messages])


async def admin_out(db: AsyncSession, ticket: models.SupportTicket, notes: list[models.SupportNote]) -> schemas.TicketAdminOut:
    detail = await ticket_detail_out(db, ticket)
    customer = await db.get(User, ticket.user_id)
    return schemas.TicketAdminOut(
        **detail.model_dump(), notes=[schemas.NoteOut.model_validate(n) for n in notes],
        customer_email=customer.email, customer_role=customer.role.value, assignee_id=ticket.assignee_id,
    )


def can_reopen(ticket: models.SupportTicket) -> bool:
    return ticket.status == models.TicketStatus.closed and ticket.closed_at is not None and now() - ticket.closed_at <= REOPEN_WINDOW
