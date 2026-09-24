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

    # PRD V1: an unused campaign pot returns to the brand's *wallet*, not to
    # their bank — so this settles immediately as an internal credit; no
    # payment-provider round-trip. Cashing out later is a separate,
    # explicit action (modules.wallet's withdrawal, 7% fee).
    reference = new_reference()
    refund = models.Refund(
        campaign_id=campaign.id,
        organisation_id=campaign.event_manager_id,
        funding_order_id=order.id,
        reference=reference,
        amount=amount,
        reason=reason,
        provider="wallet",
        requested_by=actor.id,
        status=models.RefundStatus.succeeded,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(refund)
    await db.flush()
    audit.record(
        db, "refund.succeeded", actor_id=actor.id, campaign_id=campaign.id, amount=amount, reference=reference,
    )
    return refund
