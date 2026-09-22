"""What each `DisputeType` resolves to: who may open one, how far back,
and how much money (if any) it names — the "type-specific time windows"
and "money at risk" the inventory calls for.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.auth.models import User
from modules.earnings.models import EarningEntry
from modules.funding.models import FundingOrder
from modules.payouts.models import Payout
from modules.refunds.models import Refund
from modules.submissions.models import Submission

from . import models, schemas

RESOLUTION_SLA = timedelta(days=14)


def now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ResourceFacts:
    owner_id: uuid.UUID
    reference_at: datetime
    amount: Decimal | None


async def _submission_facts(db: AsyncSession, resource_id: uuid.UUID) -> ResourceFacts | None:
    s = await db.get(Submission, resource_id)
    if s is None:
        return None
    return ResourceFacts(owner_id=s.creator_id, reference_at=s.verdict_at or s.created_at, amount=None)


async def _earning_entry_facts(db: AsyncSession, resource_id: uuid.UUID) -> ResourceFacts | None:
    e = await db.get(EarningEntry, resource_id)
    if e is None:
        return None
    return ResourceFacts(owner_id=e.creator_id, reference_at=e.accrued_at, amount=e.amount)


async def _payout_facts(db: AsyncSession, resource_id: uuid.UUID) -> ResourceFacts | None:
    p = await db.get(Payout, resource_id)
    if p is None:
        return None
    return ResourceFacts(owner_id=p.creator_id, reference_at=p.completed_at or p.initiated_at, amount=p.amount)


async def _funding_order_facts(db: AsyncSession, resource_id: uuid.UUID) -> ResourceFacts | None:
    o = await db.get(FundingOrder, resource_id)
    if o is None:
        return None
    return ResourceFacts(owner_id=o.organisation_id, reference_at=o.confirmed_at or o.created_at, amount=o.total_amount)


async def _refund_facts(db: AsyncSession, resource_id: uuid.UUID) -> ResourceFacts | None:
    r = await db.get(Refund, resource_id)
    if r is None:
        return None
    return ResourceFacts(owner_id=r.organisation_id, reference_at=r.processed_at or r.created_at, amount=r.amount)


#: (resolver, filing window from `reference_at`)
RESOURCE_TYPES = {
    models.DisputeType.submission_verdict: (_submission_facts, timedelta(days=7)),
    models.DisputeType.earning_entry: (_earning_entry_facts, timedelta(days=30)),
    models.DisputeType.payout: (_payout_facts, timedelta(days=14)),
    models.DisputeType.funding_order: (_funding_order_facts, timedelta(days=30)),
    models.DisputeType.refund: (_refund_facts, timedelta(days=30)),
}


class DisputeError(Exception):
    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def create_dispute(
    db: AsyncSession, user: User, dispute_type: models.DisputeType, resource_id: uuid.UUID, reason: str
) -> models.Dispute:
    resolver, window = RESOURCE_TYPES[dispute_type]
    facts = await resolver(db, resource_id)
    if facts is None:
        raise DisputeError("Nothing found for that reference.", 404)
    if facts.owner_id != user.id:
        raise DisputeError("Nothing found for that reference.", 404)  # don't confirm it belongs to someone else
    if now() - facts.reference_at > window:
        raise DisputeError(f"This is too old to dispute — the window is {window.days} days.")

    existing = await db.scalar(
        select(models.Dispute).where(
            models.Dispute.user_id == user.id,
            models.Dispute.type == dispute_type,
            models.Dispute.resource_id == resource_id,
            models.Dispute.status.in_((models.DisputeStatus.open, models.DisputeStatus.awaiting_customer)),
        )
    )
    if existing is not None:
        raise DisputeError("There's already an open dispute for this.")

    dispute = models.Dispute(
        user_id=user.id, type=dispute_type, resource_id=resource_id, reason=reason,
        amount_at_risk=facts.amount, deadline_at=now() + RESOLUTION_SLA,
    )
    db.add(dispute)
    await db.flush()
    return dispute


async def unread_count(db: AsyncSession, dispute: models.Dispute) -> int:
    return (
        await db.scalar(
            select(func.count()).select_from(models.DisputeMessage).where(
                models.DisputeMessage.dispute_id == dispute.id,
                models.DisputeMessage.from_admin.is_(True),
                models.DisputeMessage.created_at > dispute.customer_last_read_at,
            )
        )
    ) or 0


async def out(db: AsyncSession, dispute: models.Dispute) -> schemas.DisputeOut:
    return schemas.DisputeOut(
        id=dispute.id, type=dispute.type, resource_id=dispute.resource_id, reason=dispute.reason,
        status=dispute.status, amount_at_risk=dispute.amount_at_risk, deadline_at=dispute.deadline_at,
        resolution=dispute.resolution, resolution_note=dispute.resolution_note,
        unread_count=await unread_count(db, dispute), created_at=dispute.created_at, updated_at=dispute.updated_at,
        resolved_at=dispute.resolved_at,
    )


async def detail_out(db: AsyncSession, dispute: models.Dispute) -> schemas.DisputeDetailOut:
    base = await out(db, dispute)
    return schemas.DisputeDetailOut(
        **base.model_dump(), messages=[schemas.DisputeMessageOut.model_validate(m) for m in dispute.messages]
    )


async def admin_out(db: AsyncSession, dispute: models.Dispute) -> schemas.DisputeAdminOut:
    detail = await detail_out(db, dispute)
    customer = await db.get(User, dispute.user_id)
    return schemas.DisputeAdminOut(
        **detail.model_dump(), assignee_id=dispute.assignee_id, customer_role=customer.role.value
    )
