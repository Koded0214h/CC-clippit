"""Refunding a campaign's unused pot. See `models.Refund`'s docstring for
the one assumption baked in here (the funding fee is never refunded).
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.money import ZERO
from integrations.payments import get_provider
from integrations.payments.base import ProviderError, TransferStatus
from modules.audit import service as audit
from modules.auth.models import User
from modules.campaigns import models as campaign_models
from modules.campaigns.service import spent_by_campaign
from modules.funding import models as funding_models
from modules.funding.service import latest_order

from . import models


class RefundError(Exception):
    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def new_reference() -> str:
    return f"RFD-{datetime.now(timezone.utc):%y%m}-{secrets.token_hex(3).upper()}"


async def refundable_amount(db: AsyncSession, campaign: campaign_models.Campaign):
    """The unused pot — never the funding fee (see models.Refund). Only
    meaningful once the campaign has actually stopped spending."""
    spent = (await spent_by_campaign(db, [campaign.id])).get(campaign.id, ZERO)
    return max(campaign.pot_amount - spent, ZERO)


async def create_refund(
    db: AsyncSession, campaign: campaign_models.Campaign, actor: User, *, reason: str
) -> models.Refund:
    if campaign.status != campaign_models.CampaignStatus.closed:
        raise RefundError("A campaign can only be refunded after it's closed.")
    existing = await db.scalar(
        select(models.Refund).where(
            models.Refund.campaign_id == campaign.id,
            models.Refund.status.in_((models.RefundStatus.pending, models.RefundStatus.processing, models.RefundStatus.succeeded)),
        )
    )
    if existing is not None:
        return existing  # idempotent: one live/completed refund per campaign

    order = await latest_order(db, campaign.id)
    if order is None or order.status != funding_models.FundingStatus.confirmed:
        raise RefundError("This campaign was never confirmed as funded — there's nothing to refund.")
    amount = await refundable_amount(db, campaign)
    if amount <= ZERO:
        raise RefundError("There's nothing left to refund — the pot was fully spent.")

    provider = get_provider()
    reference = new_reference()
    refund = models.Refund(
        campaign_id=campaign.id,
        organisation_id=campaign.event_manager_id,
        funding_order_id=order.id,
        reference=reference,
        amount=amount,
        reason=reason,
        provider=provider.name,
        requested_by=actor.id,
        status=models.RefundStatus.processing,
    )
    db.add(refund)
    await db.flush()
    audit.record(
        db, "refund.requested", actor_id=actor.id, campaign_id=campaign.id, amount=amount, reference=reference,
    )

    try:
        result = await provider.create_refund(
            reference=reference, collection_reference=order.reference, amount=amount, reason=reason
        )
    except ProviderError as exc:
        refund.status = models.RefundStatus.failed
        refund.failure_reason = str(exc)
        audit.record(db, "refund.failed", actor_id=actor.id, campaign_id=campaign.id, reference=reference, reason=str(exc))
        return refund

    refund.provider_reference = result.provider_reference
    if result.status == TransferStatus.success:
        refund.status = models.RefundStatus.succeeded
        refund.processed_at = datetime.now(timezone.utc)
        audit.record(db, "refund.succeeded", actor_id=actor.id, campaign_id=campaign.id, reference=reference, amount=amount)
    elif result.status == TransferStatus.failed:
        refund.status = models.RefundStatus.failed
        refund.failure_reason = result.failure_reason
        audit.record(db, "refund.failed", actor_id=actor.id, campaign_id=campaign.id, reference=reference, reason=result.failure_reason)
    # else: stays `processing` — Paystack has no reconciliation lookup for
    # refunds yet (see integrations.payments.paystack.get_refund); an
    # admin retry/fail path is still open (production-api-inventory.md §J).
    return refund
