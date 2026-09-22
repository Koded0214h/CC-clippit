"""The brand's own read of its money: every funding order and refund
against its campaigns, in one immutable, server-derived list — the
"transactions" screen currently fabricates this client-side.

Deliberately not a new table: a `FundingOrder` or `Refund` row already is
the immutable ledger entry; this just presents the two together in one
shape and one order. Creator payouts are not included here — from the
brand's side of the ledger, the pot was already spent in full at funding
time; where it went afterwards is the creator's own earnings/payout
history, not a second movement of the brand's money.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.campaigns.models import Campaign
from modules.funding.models import FundingOrder
from modules.refunds.models import Refund


@dataclass
class TransactionRow:
    id: uuid.UUID
    kind: str  # "funding" | "refund"
    campaign_id: uuid.UUID
    campaign_title: str
    amount: Decimal
    fee: Decimal | None
    status: str
    provider: str
    provider_reference: str | None
    reference: str
    created_at: datetime
    settled_at: datetime | None


async def _campaign_titles(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    return {c.id: c.title for c in await db.scalars(select(Campaign).where(Campaign.id.in_(ids)))}


async def list_transactions(
    db: AsyncSession, organisation_id: uuid.UUID, *, campaign_id: uuid.UUID | None, kind: str | None, limit: int, offset: int
) -> tuple[list[TransactionRow], int]:
    orders = list(await db.scalars(select(FundingOrder).where(FundingOrder.organisation_id == organisation_id)))
    refunds = list(await db.scalars(select(Refund).where(Refund.organisation_id == organisation_id)))
    titles = await _campaign_titles(db, {o.campaign_id for o in orders} | {r.campaign_id for r in refunds})

    rows = [
        TransactionRow(
            id=o.id, kind="funding", campaign_id=o.campaign_id, campaign_title=titles.get(o.campaign_id, ""),
            amount=o.total_amount, fee=o.fee_amount, status=o.status.value, provider=o.provider,
            provider_reference=o.provider_reference, reference=o.reference, created_at=o.created_at,
            settled_at=o.confirmed_at,
        )
        for o in orders
    ] + [
        TransactionRow(
            id=r.id, kind="refund", campaign_id=r.campaign_id, campaign_title=titles.get(r.campaign_id, ""),
            amount=r.amount, fee=None, status=r.status.value, provider=r.provider,
            provider_reference=r.provider_reference, reference=r.reference, created_at=r.created_at,
            settled_at=r.processed_at,
        )
        for r in refunds
    ]
    if campaign_id:
        rows = [r for r in rows if r.campaign_id == campaign_id]
    if kind:
        rows = [r for r in rows if r.kind == kind]
    rows.sort(key=lambda r: r.created_at, reverse=True)
    return rows[offset : offset + limit], len(rows)


async def get_transaction(db: AsyncSession, organisation_id: uuid.UUID, transaction_id: uuid.UUID) -> TransactionRow | None:
    rows, _ = await list_transactions(db, organisation_id, campaign_id=None, kind=None, limit=10_000, offset=0)
    return next((r for r in rows if r.id == transaction_id), None)
