"""Withdrawals: moving a creator's payable earnings to their bank.

The order of operations is the whole safety story:

1. **Reserve** — inside one transaction, under a lock on the creator, check
   the amount against what is genuinely payable and record the payout plus the
   exact earning entries it consumes. Commit. The money is now spoken for, and
   a second request (double tap, another tab) cannot reserve it again.
2. **Send** — only after that commit, ask the provider to transfer, using the
   payout's `reference` as the provider-side idempotency key. If we crash
   between 1 and 2, the payout is `pending` and the reconciliation job sends
   it; the provider de-duplicates on the reference, so it cannot go twice.
3. **Settle** — success finishes the payout; a refusal or bounce marks it
   `failed`, which returns the reserved money to `payable` simply by no longer
   counting the allocation. Money is never deleted or "put back" by hand.

`payable` itself is derived in `earnings.queries.balances`; nothing here
keeps a separate running balance that could drift.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.money import ZERO, quantize, to_decimal
from integrations.payments import get_provider
from integrations.payments.base import (
    ProviderError,
    TransferRejected,
    TransferStatus,
    WebhookEvent,
    WebhookKind,
)
from modules.audit import service as audit
from modules.auth.models import User
from modules.campaigns.models import Campaign
from modules.creators.models import CreatorBankAccount
from modules.earnings import queries as earnings_queries
from modules.earnings.models import EarningAccount, EarningEntry
from modules.notifications.service import notify
from modules.submissions.models import Submission

from . import models, schemas

LIVE = (models.PayoutStatus.pending, models.PayoutStatus.processing, models.PayoutStatus.succeeded)


class PayoutError(Exception):
    def __init__(self, message: str, status_code: int = 409, code: str = "payout_error") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_reference() -> str:
    return f"CLP-{_now():%y%m%d}-{secrets.randbelow(9000) + 1000}"


def mask(number: str) -> str:
    return "*" * max(len(number) - 4, 0) + number[-4:]


# --- 1. reserve ---------------------------------------------------------------------


async def reserve(
    db: AsyncSession, creator: User, amount: Decimal, idempotency_key: str
) -> tuple[models.Payout, bool]:
    """Returns (payout, created). `created` is False when this idempotency key
    was already used — the earlier payout is returned untouched."""
    settings = get_settings()

    existing = await db.scalar(
        select(models.Payout).where(models.Payout.creator_id == creator.id, models.Payout.idempotency_key == idempotency_key)
    )
    if existing:
        if quantize(existing.amount) != quantize(amount):
            raise PayoutError("That request key was already used for a different amount.", 409, "idempotency_conflict")
        return existing, False

    if creator.suspended_at is not None and "earning" in creator.suspension_scopes:
        raise PayoutError("Withdrawals are suspended on this account.", 403, "account_suspended")

    amount = quantize(amount)
    if amount < settings.min_withdrawal:
        raise PayoutError(f"The minimum withdrawal is ₦{settings.min_withdrawal:,}.", 422, "below_minimum")

    bank = await db.get(CreatorBankAccount, creator.id)
    if bank is None or not bank.verified or not bank.account_name:
        raise PayoutError("Verify your bank account before withdrawing.", 409, "bank_not_verified")

    # Serialise this creator's withdrawals. Without the lock, two requests
    # could each see the full balance and both reserve it.
    await db.scalar(select(User.id).where(User.id == creator.id).with_for_update())

    at = _now()
    payable = (await earnings_queries.balances(db, creator.id, at)).payable
    if amount > payable:
        raise PayoutError(f"You only have ₦{payable:,.2f} available to withdraw.", 409, "insufficient_payable")

    entries = list(
        await db.scalars(
            select(EarningEntry)
            .join(EarningAccount, EarningAccount.submission_id == EarningEntry.submission_id)
            .where(
                EarningEntry.creator_id == creator.id, EarningEntry.payable_at <= at,
                EarningAccount.release_hold_at.is_(None),  # see EarningAccount.release_hold_at's docstring
            )
            .order_by(EarningEntry.payable_at.asc(), EarningEntry.accrued_at.asc())
        )
    )
    used: dict[uuid.UUID, Decimal] = {
        eid: to_decimal(total)
        for eid, total in await db.execute(
            select(models.PayoutAllocation.entry_id, func.coalesce(func.sum(models.PayoutAllocation.amount), 0))
            .join(models.Payout, models.Payout.id == models.PayoutAllocation.payout_id)
            .where(models.Payout.creator_id == creator.id, models.Payout.status.in_(LIVE))
            .group_by(models.PayoutAllocation.entry_id)
        )
    }

    reference = new_reference()
    while await db.scalar(select(models.Payout.id).where(models.Payout.reference == reference)):
        reference = new_reference()

    provider = get_provider()
    payout = models.Payout(
        creator_id=creator.id, reference=reference, idempotency_key=idempotency_key, amount=amount, fee=ZERO,
        provider=provider.name, bank_code=bank.bank_code, bank_name=bank.bank_name,
        account_number=bank.account_number, account_name=bank.account_name,
    )
    db.add(payout)
    await db.flush()

    need = amount
    for entry in entries:  # oldest earnings leave first
        if need <= 0:
            break
        free = entry.amount - used.get(entry.id, ZERO)
        take = min(free, need)
        if take > 0:
            db.add(models.PayoutAllocation(payout_id=payout.id, entry_id=entry.id, amount=take))
            need -= take
    if need > 0:  # the balance said yes but the entries said no: refuse rather than send money we can't trace
        raise PayoutError("We couldn't reserve that amount. Try again.", 409, "reserve_failed")

    audit.record(db, "payout.reserved", actor_id=creator.id, subject_id=creator.id, amount=amount, reference=reference)
    return payout, True


# --- 2. send ------------------------------------------------------------------------------


async def dispatch(db: AsyncSession, payout_id: uuid.UUID) -> models.Payout:
    """Asks the provider to send a `pending` payout. Safe to call again for
    the same payout: the provider keys on `reference`."""
    payout = await db.scalar(select(models.Payout).where(models.Payout.id == payout_id).with_for_update())
    if payout is None or payout.status != models.PayoutStatus.pending:
        return payout

    provider = get_provider()
    try:
        result = await provider.create_transfer(
            reference=payout.reference,
            amount=payout.amount - payout.fee,
            account_number=payout.account_number,
            bank_code=payout.bank_code,
            account_name=payout.account_name,
            narration=f"Clippit payout {payout.reference}",
        )
    except TransferRejected as exc:
        await fail(db, payout, str(exc))
        return payout
    except ProviderError as exc:
        # Unknown outcome: stay pending. Reconciliation retries with the same reference.
        audit.record(db, "payout.dispatch_unreachable", subject_id=payout.creator_id, reference=payout.reference, error=str(exc))
        return payout

    payout.provider_reference = result.provider_reference
    if result.status == TransferStatus.success:
        await succeed(db, payout)
    elif result.status == TransferStatus.failed:
        await fail(db, payout, result.failure_reason or "The transfer failed.")
    else:
        payout.status = models.PayoutStatus.processing
        audit.record(db, "payout.processing", subject_id=payout.creator_id, reference=payout.reference)
    return payout


# --- 3. settle ---------------------------------------------------------------------------


async def succeed(db: AsyncSession, payout: models.Payout) -> None:
    if payout.status == models.PayoutStatus.succeeded:
        return
    payout.status = models.PayoutStatus.succeeded
    payout.completed_at = _now()
    audit.record(db, "payout.succeeded", subject_id=payout.creator_id, amount=payout.amount, reference=payout.reference)
    await notify(
        db, payout.creator_id, "payout", "Transfer successful",
        f"₦{payout.amount:,.0f} was sent to {payout.bank_name} ending {payout.account_number[-4:]}.",
        link=f"/dashboard/payouts/receipt?id={payout.id}",
    )


async def fail(db: AsyncSession, payout: models.Payout, reason: str) -> None:
    """Marks the payout failed. Its allocations stop counting, which is what
    returns the money to the creator's payable balance."""
    if payout.status in (models.PayoutStatus.failed, models.PayoutStatus.succeeded):
        return
    payout.status = models.PayoutStatus.failed
    payout.failure_reason = reason
    payout.completed_at = _now()
    audit.record(db, "payout.failed", subject_id=payout.creator_id, amount=payout.amount, reference=payout.reference, reason=reason)
    await notify(
        db, payout.creator_id, "payout", "Withdrawal failed",
        f"₦{payout.amount:,.0f} couldn't be sent: {reason} The money is back in your payable balance.",
        link="/dashboard/earnings",
    )


async def apply_transfer_event(db: AsyncSession, event: WebhookEvent) -> bool:
    """A provider's transfer webhook. Only moves a payout that is still in
    flight, so a late or replayed event can't flip a settled one."""
    payout = await db.scalar(select(models.Payout).where(models.Payout.reference == event.reference).with_for_update())
    if payout is None:
        return False
    if payout.status not in (models.PayoutStatus.pending, models.PayoutStatus.processing):
        if payout.status == models.PayoutStatus.succeeded and event.kind == WebhookKind.transfer_failed:
            # A settled transfer that the provider now says bounced or was
            # reversed. The money already left, so this is not something to
            # auto-undo — it is something an admin must see.
            audit.record(
                db, "payout.reversed_after_success", subject_id=payout.creator_id, amount=payout.amount,
                reference=payout.reference, reason=event.failure_reason,
            )
        return True  # already settled; acknowledged
    if event.provider_reference:
        payout.provider_reference = event.provider_reference
    if event.kind == WebhookKind.transfer_success:
        await succeed(db, payout)
    elif event.kind == WebhookKind.transfer_failed:
        await fail(db, payout, event.failure_reason or "The transfer failed.")
    else:
        return False
    return True


async def reconcile(db: AsyncSession, *, older_than: timedelta = timedelta(minutes=2), limit: int = 100) -> int:
    """Re-drives payouts stuck in flight: a `pending` one was never sent (we
    crashed between reserve and send) and is sent now; a `processing` one is
    asked about. Returns how many it moved."""
    cutoff = _now() - older_than
    stuck = list(
        await db.scalars(
            select(models.Payout)
            .where(
                models.Payout.status.in_((models.PayoutStatus.pending, models.PayoutStatus.processing)),
                models.Payout.updated_at <= cutoff,
            )
            .order_by(models.Payout.initiated_at.asc())
            .limit(limit)
        )
    )
    moved = 0
    provider = get_provider()
    for payout in stuck:
        before = payout.status
        if payout.status == models.PayoutStatus.pending:
            await dispatch(db, payout.id)
        else:
            try:
                result = await provider.get_transfer(reference=payout.reference)
            except ProviderError:
                continue
            if result.status == TransferStatus.success:
                await succeed(db, payout)
            elif result.status == TransferStatus.failed:
                await fail(db, payout, result.failure_reason or "The transfer failed.")
        await db.commit()
        moved += payout.status != before
    return moved


# --- presenting ------------------------------------------------------------------------------


async def present(db: AsyncSession, payouts: list[models.Payout], *, with_provenance: bool) -> list[schemas.PayoutOut]:
    if not payouts:
        return []
    provider = get_provider()
    names = {u.id: u.full_name for u in await db.scalars(select(User).where(User.id.in_({p.creator_id for p in payouts})))}

    provenance: dict[uuid.UUID, schemas.Provenance] = {}
    if with_provenance:
        rows = (
            await db.execute(
                select(
                    models.PayoutAllocation.payout_id, models.PayoutAllocation.amount, EarningEntry.billable_views,
                    Submission.id, Submission.title, Campaign.title,
                )
                .join(EarningEntry, EarningEntry.id == models.PayoutAllocation.entry_id)
                .join(Submission, Submission.id == EarningEntry.submission_id)
                .join(Campaign, Campaign.id == EarningEntry.campaign_id)
                .where(models.PayoutAllocation.payout_id.in_([p.id for p in payouts]))
            )
        ).all()
        grouped: dict[uuid.UUID, list] = {}
        for row in rows:
            grouped.setdefault(row[0], []).append(row)
        for pid, items in grouped.items():
            provenance[pid] = schemas.Provenance(
                approved_clips=len({r[3] for r in items}),
                campaigns=sorted({r[5] for r in items}),
                billable_views=int(sum(r[2] for r in items)),
                sources=[schemas.SourceRow(campaign_title=r[5], clip=r[4] or "Untitled clip", amount=r[1]) for r in items],
            )

    return [
        schemas.PayoutOut(
            id=p.id, reference=p.reference, status=p.status, amount=p.amount, fee=p.fee, net=p.amount - p.fee,
            creator_name=names.get(p.creator_id, ""),
            destination=schemas.BankDestination(
                bank_code=p.bank_code, bank_name=p.bank_name, account_number_masked=mask(p.account_number),
                account_name=p.account_name,
            ),
            provider=p.provider, sandbox=provider.sandbox, failure_reason=p.failure_reason,
            initiated_at=p.initiated_at, completed_at=p.completed_at, provenance=provenance.get(p.id),
        )
        for p in payouts
    ]
