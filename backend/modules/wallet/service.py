"""The brand wallet: `available_balance` is a projection over two existing
immutable tables (`Refund`, `OrganisationWithdrawal`), never a stored
number — same discipline as creator earnings (D26). `reserved_balance` is
likewise a projection over the brand's own non-closed campaigns, reusing
`campaigns.service.spent_by_campaign` rather than a separate ledger.

Withdrawal follows the exact reserve → send → settle shape
`modules.payouts.service` uses for creators, just without an allocation
table: a brand's balance isn't earned in traceable increments, so there's
nothing to allocate — only a lock (on the organisation's own user row) to
serialise concurrent withdrawal requests against the same projected
balance.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.money import ZERO, quantize, to_decimal
from integrations.payments import get_provider
from integrations.payments.base import ProviderError, TransferRejected, TransferStatus, WebhookEvent, WebhookKind
from modules.audit import service as audit
from modules.auth.models import User
from modules.campaigns import models as campaign_models
from modules.campaigns import service as campaign_service
from modules.notifications.service import notify
from modules.organisations.models import OrganisationBankAccount
from modules.refunds.models import Refund, RefundStatus

from . import models

LIVE = (models.WithdrawalStatus.pending, models.WithdrawalStatus.processing, models.WithdrawalStatus.succeeded)


class WalletError(Exception):
    def __init__(self, message: str, status_code: int = 409, code: str = "wallet_error") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_reference() -> str:
    return f"CLW-{_now():%y%m%d}-{secrets.randbelow(9000) + 1000}"


def mask(number: str) -> str:
    return "*" * max(len(number) - 4, 0) + number[-4:]


@dataclass
class BrandBalance:
    available: Decimal
    reserved: Decimal
    withdrawn: Decimal


async def brand_balance(db: AsyncSession, organisation_id: uuid.UUID) -> BrandBalance:
    refunded = to_decimal(
        await db.scalar(
            select(func.coalesce(func.sum(Refund.amount), 0)).where(
                Refund.organisation_id == organisation_id, Refund.status == RefundStatus.succeeded
            )
        )
    )
    withdrawn_live = to_decimal(
        await db.scalar(
            select(func.coalesce(func.sum(models.OrganisationWithdrawal.amount), 0)).where(
                models.OrganisationWithdrawal.organisation_id == organisation_id,
                models.OrganisationWithdrawal.status.in_(LIVE),
            )
        )
    )
    withdrawn_paid = to_decimal(
        await db.scalar(
            select(func.coalesce(func.sum(models.OrganisationWithdrawal.amount), 0)).where(
                models.OrganisationWithdrawal.organisation_id == organisation_id,
                models.OrganisationWithdrawal.status == models.WithdrawalStatus.succeeded,
            )
        )
    )

    campaigns = list(
        await db.scalars(
            select(campaign_models.Campaign).where(
                campaign_models.Campaign.event_manager_id == organisation_id,
                campaign_models.Campaign.status.in_(
                    (campaign_models.CampaignStatus.pending_funding, campaign_models.CampaignStatus.active)
                ),
            )
        )
    )
    spent = await campaign_service.spent_by_campaign(db, [c.id for c in campaigns])
    reserved = sum((c.pot_amount - spent.get(c.id, ZERO) for c in campaigns), ZERO)

    return BrandBalance(available=refunded - withdrawn_live, reserved=reserved, withdrawn=withdrawn_paid)


async def reserve(
    db: AsyncSession, organisation: User, amount: Decimal, idempotency_key: str
) -> tuple[models.OrganisationWithdrawal, bool]:
    settings = get_settings()

    existing = await db.scalar(
        select(models.OrganisationWithdrawal).where(
            models.OrganisationWithdrawal.organisation_id == organisation.id,
            models.OrganisationWithdrawal.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if quantize(existing.amount) != quantize(amount):
            raise WalletError("That request key was already used for a different amount.", 409, "idempotency_conflict")
        return existing, False

    if organisation.suspended_at is not None and "earning" in organisation.suspension_scopes:
        raise WalletError("Withdrawals are suspended on this account.", 403, "account_suspended")

    amount = quantize(amount)
    if amount < settings.min_withdrawal:
        raise WalletError(f"The minimum withdrawal is ₦{settings.min_withdrawal:,}.", 422, "below_minimum")

    bank = await db.get(OrganisationBankAccount, organisation.id)
    if bank is None or not bank.verified or not bank.account_name:
        raise WalletError("Verify your bank account before withdrawing.", 409, "bank_not_verified")

    # Serialise this organisation's withdrawals against the same projected
    # balance — same reasoning as payouts.service.reserve's creator lock.
    await db.scalar(select(User.id).where(User.id == organisation.id).with_for_update())

    balance = await brand_balance(db, organisation.id)
    if amount > balance.available:
        raise WalletError(f"You only have ₦{balance.available:,.2f} available to withdraw.", 409, "insufficient_available")

    reference = new_reference()
    while await db.scalar(select(models.OrganisationWithdrawal.id).where(models.OrganisationWithdrawal.reference == reference)):
        reference = new_reference()

    provider = get_provider()
    fee = quantize(amount * to_decimal(settings.withdrawal_fee_rate))
    withdrawal = models.OrganisationWithdrawal(
        organisation_id=organisation.id, reference=reference, idempotency_key=idempotency_key, amount=amount, fee=fee,
        provider=provider.name, bank_code=bank.bank_code, bank_name=bank.bank_name,
        account_number=bank.account_number, account_name=bank.account_name,
    )
    db.add(withdrawal)
    await db.flush()
    audit.record(db, "wallet.withdrawal_reserved", actor_id=organisation.id, subject_id=organisation.id, amount=amount, reference=reference)
    return withdrawal, True


async def dispatch(db: AsyncSession, withdrawal_id: uuid.UUID) -> models.OrganisationWithdrawal:
    withdrawal = await db.scalar(
        select(models.OrganisationWithdrawal).where(models.OrganisationWithdrawal.id == withdrawal_id).with_for_update()
    )
    if withdrawal is None or withdrawal.status != models.WithdrawalStatus.pending:
        return withdrawal

    provider = get_provider()
    try:
        result = await provider.create_transfer(
            reference=withdrawal.reference,
            amount=withdrawal.amount - withdrawal.fee,
            account_number=withdrawal.account_number,
            bank_code=withdrawal.bank_code,
            account_name=withdrawal.account_name,
            narration=f"Clippit wallet withdrawal {withdrawal.reference}",
        )
    except TransferRejected as exc:
        await fail(db, withdrawal, str(exc))
        return withdrawal
    except ProviderError as exc:
        audit.record(db, "wallet.withdrawal_dispatch_unreachable", subject_id=withdrawal.organisation_id, reference=withdrawal.reference, error=str(exc))
        return withdrawal

    withdrawal.provider_reference = result.provider_reference
    if result.status == TransferStatus.success:
        await succeed(db, withdrawal)
    elif result.status == TransferStatus.failed:
        await fail(db, withdrawal, result.failure_reason or "The transfer failed.")
    else:
        withdrawal.status = models.WithdrawalStatus.processing
        audit.record(db, "wallet.withdrawal_processing", subject_id=withdrawal.organisation_id, reference=withdrawal.reference)
    return withdrawal


async def succeed(db: AsyncSession, withdrawal: models.OrganisationWithdrawal) -> None:
    if withdrawal.status == models.WithdrawalStatus.succeeded:
        return
    withdrawal.status = models.WithdrawalStatus.succeeded
    withdrawal.completed_at = _now()
    audit.record(db, "wallet.withdrawal_succeeded", subject_id=withdrawal.organisation_id, amount=withdrawal.amount, reference=withdrawal.reference)
    await notify(
        db, withdrawal.organisation_id, "wallet", "Withdrawal successful",
        f"₦{withdrawal.amount:,.0f} was sent to {withdrawal.bank_name} ending {withdrawal.account_number[-4:]}.",
        link="/brand/wallet",
    )


async def fail(db: AsyncSession, withdrawal: models.OrganisationWithdrawal, reason: str) -> None:
    if withdrawal.status in (models.WithdrawalStatus.failed, models.WithdrawalStatus.succeeded):
        return
    withdrawal.status = models.WithdrawalStatus.failed
    withdrawal.failure_reason = reason
    withdrawal.completed_at = _now()
    audit.record(db, "wallet.withdrawal_failed", subject_id=withdrawal.organisation_id, amount=withdrawal.amount, reference=withdrawal.reference, reason=reason)
    await notify(
        db, withdrawal.organisation_id, "wallet", "Withdrawal failed",
        f"₦{withdrawal.amount:,.0f} couldn't be sent: {reason} The money is back in your wallet.",
        link="/brand/wallet",
    )


async def apply_transfer_event(db: AsyncSession, event: WebhookEvent) -> bool:
    """Mirrors `payouts.service.apply_transfer_event` for the wallet side.
    Only called once the reference has already been checked against
    `Payout` and not found — see `modules.payments.router`."""
    withdrawal = await db.scalar(
        select(models.OrganisationWithdrawal).where(models.OrganisationWithdrawal.reference == event.reference).with_for_update()
    )
    if withdrawal is None:
        return False
    if withdrawal.status not in (models.WithdrawalStatus.pending, models.WithdrawalStatus.processing):
        if withdrawal.status == models.WithdrawalStatus.succeeded and event.kind == WebhookKind.transfer_failed:
            audit.record(
                db, "wallet.withdrawal_reversed_after_success", subject_id=withdrawal.organisation_id, amount=withdrawal.amount,
                reference=withdrawal.reference, reason=event.failure_reason,
            )
        return True
    if event.provider_reference:
        withdrawal.provider_reference = event.provider_reference
    if event.kind == WebhookKind.transfer_success:
        await succeed(db, withdrawal)
    elif event.kind == WebhookKind.transfer_failed:
        await fail(db, withdrawal, event.failure_reason or "The transfer failed.")
    return True


async def reconcile_one(db: AsyncSession, withdrawal: models.OrganisationWithdrawal) -> bool:
    """Mirrors `payouts.service.reconcile_one` for the wallet side."""
    before = withdrawal.status
    if withdrawal.status == models.WithdrawalStatus.pending:
        await dispatch(db, withdrawal.id)
    elif withdrawal.status == models.WithdrawalStatus.processing:
        provider = get_provider()
        try:
            result = await provider.get_transfer(reference=withdrawal.reference)
        except ProviderError:
            return False
        if result.status == TransferStatus.success:
            await succeed(db, withdrawal)
        elif result.status == TransferStatus.failed:
            await fail(db, withdrawal, result.failure_reason or "The transfer failed.")
    return withdrawal.status != before


async def reconcile(db: AsyncSession, *, older_than: timedelta = timedelta(minutes=2), limit: int = 100) -> int:
    cutoff = _now() - older_than
    stuck = list(
        await db.scalars(
            select(models.OrganisationWithdrawal)
            .where(
                models.OrganisationWithdrawal.status.in_((models.WithdrawalStatus.pending, models.WithdrawalStatus.processing)),
                models.OrganisationWithdrawal.updated_at <= cutoff,
            )
            .order_by(models.OrganisationWithdrawal.initiated_at.asc())
            .limit(limit)
        )
    )
    moved = 0
    for withdrawal in stuck:
        changed = await reconcile_one(db, withdrawal)
        await db.commit()
        moved += changed
    return moved
