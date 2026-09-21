"""Turning a brand's payment into an open campaign.

The order freezes what the brand was quoted. Confirmation — by asking the
provider, or by the provider's signed webhook — is the only thing that flips
the campaign to `active`; a brand's own claim ("I have funded the pot") never
opens it on its own.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.money import quantize, to_decimal
from integrations.payments import get_provider
from integrations.payments.base import PaymentProvider, ProviderError
from modules.audit import service as audit
from modules.auth.models import User
from modules.campaigns import models as campaign_models
from modules.campaigns.service import brands, now
from modules.notifications.service import notify

from . import models, schemas

DEFAULT_DURATION_DAYS = 14


class FundingError(Exception):
    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def new_reference() -> str:
    return f"CLP-{datetime.now(timezone.utc):%y%m}-{secrets.token_hex(2).upper()}"


async def latest_order(db: AsyncSession, campaign_id) -> models.FundingOrder | None:
    return await db.scalar(
        select(models.FundingOrder)
        .where(models.FundingOrder.campaign_id == campaign_id)
        .order_by(models.FundingOrder.created_at.desc())
        .limit(1)
    )


def order_out(order: models.FundingOrder, campaign: campaign_models.Campaign, provider: PaymentProvider) -> schemas.FundingOrderOut:
    collection = None
    if order.collection_account_number:
        collection = schemas.CollectionOut(
            bank_name=order.collection_bank_name or "",
            account_number=order.collection_account_number,
            account_name=order.collection_account_name or "",
        )
    return schemas.FundingOrderOut(
        id=order.id,
        campaign_id=order.campaign_id,
        reference=order.reference,
        status=order.status,
        method=order.method,
        pot=order.pot_amount,
        fee=order.fee_amount,
        total=order.total_amount,
        provider=order.provider,
        sandbox=provider.sandbox,
        provider_reference=order.provider_reference,
        collection=collection,
        campaign_status=campaign.status.value,
        created_at=order.created_at,
        confirmed_at=order.confirmed_at,
    )


def _check_fundable(campaign: campaign_models.Campaign) -> None:
    if campaign.status not in (campaign_models.CampaignStatus.draft, campaign_models.CampaignStatus.pending_funding):
        raise FundingError(f"This campaign is already {campaign.status.value}.")
    if campaign.payout_rule is None:
        raise FundingError("Set the payout rate before funding this campaign.")
    if campaign.pot_amount <= 0:
        raise FundingError("Set a campaign pot before funding.")


async def create_order(
    db: AsyncSession, campaign: campaign_models.Campaign, org: User, method: models.FundingMethod
) -> models.FundingOrder:
    """The open order for this campaign — reused if there is one, so a
    double-click (or a page reload) never mints two collection accounts."""
    _check_fundable(campaign)
    provider = get_provider()

    existing = await latest_order(db, campaign.id)
    if existing and existing.status in (models.FundingStatus.awaiting_payment, models.FundingStatus.awaiting_confirmation):
        if existing.method == method:
            return existing
        if existing.status == models.FundingStatus.awaiting_confirmation:
            raise FundingError("Payment is already awaiting confirmation; contact support to change the method.")
        existing.status = models.FundingStatus.cancelled
        await db.flush()

    pot = campaign.pot_amount
    fee = quantize(pot * to_decimal(get_settings().funding_fee_rate))
    total = pot + fee

    reference = new_reference()
    while await db.scalar(select(models.FundingOrder.id).where(models.FundingOrder.reference == reference)):
        reference = new_reference()

    account = None
    if method == models.FundingMethod.bank:
        brand = (await brands(db, {org.id})).get(org.id)
        try:
            account = await provider.create_collection(
                reference=reference, amount=total, description=(brand.name if brand else org.full_name)
            )
        except ProviderError as exc:
            raise FundingError("We couldn't set up payment right now. Try again in a moment.", 502) from exc

    order = models.FundingOrder(
        campaign_id=campaign.id,
        organisation_id=campaign.event_manager_id,
        reference=reference,
        method=method,
        pot_amount=pot,
        fee_amount=fee,
        total_amount=total,
        provider=provider.name,
        provider_reference=account.provider_reference if account else None,
        collection_bank_name=account.bank_name if account else None,
        collection_account_number=account.account_number if account else None,
        collection_account_name=account.account_name if account else None,
    )
    db.add(order)
    campaign.status = campaign_models.CampaignStatus.pending_funding
    await db.flush()
    audit.record(
        db, "funding.order_created", actor_id=org.id, campaign_id=campaign.id, amount=total,
        reference=reference, method=method.value,
    )
    return order


async def cancel_order(db: AsyncSession, campaign: campaign_models.Campaign, actor: User) -> models.FundingOrder:
    order = await latest_order(db, campaign.id)
    if order is None or order.status != models.FundingStatus.awaiting_payment:
        raise FundingError("There's no unpaid funding order to cancel.")
    order.status = models.FundingStatus.cancelled
    campaign.status = campaign_models.CampaignStatus.draft
    audit.record(db, "funding.order_cancelled", actor_id=actor.id, campaign_id=campaign.id, reference=order.reference)
    return order


async def open_campaign(db: AsyncSession, campaign: campaign_models.Campaign, *, actor_id) -> None:
    """Funded → live. The clock (`ends_at`) starts here, not at creation, so
    a campaign that sat in draft doesn't lose days."""
    started = now()
    days = campaign.duration_days or DEFAULT_DURATION_DAYS
    campaign.status = campaign_models.CampaignStatus.active
    campaign.activated_at = started
    campaign.ends_at = started + timedelta(days=days)
    campaign.accepting_entries = True
    audit.record(db, "campaign.opened", actor_id=actor_id, campaign_id=campaign.id, days=days)


async def mark_confirmed(
    db: AsyncSession, order: models.FundingOrder, campaign: campaign_models.Campaign, *, actor_id, amount: Decimal | None = None
) -> bool:
    """Idempotent. Returns True only the first time, so a duplicate webhook
    can't open the campaign (or notify) twice."""
    if order.status == models.FundingStatus.confirmed:
        return False
    if amount is not None and amount < order.total_amount:
        # Short payment: keep waiting rather than opening an under-funded pot.
        order.status = models.FundingStatus.awaiting_confirmation
        audit.record(db, "funding.short_payment", campaign_id=campaign.id, amount=amount, expected=order.total_amount)
        return False
    order.status = models.FundingStatus.confirmed
    order.confirmed_at = now()
    if campaign.status in (campaign_models.CampaignStatus.draft, campaign_models.CampaignStatus.pending_funding):
        await open_campaign(db, campaign, actor_id=actor_id)
    audit.record(
        db, "funding.confirmed", actor_id=actor_id, campaign_id=campaign.id, amount=order.total_amount,
        reference=order.reference,
    )
    await notify(
        db,
        campaign.event_manager_id,
        "funding",
        "Campaign funded",
        f"{campaign.title} is live. Creators can now join and submit clips.",
        link=f"/brand/campaigns/{campaign.slug}",
    )
    return True


async def confirm_with_provider(
    db: AsyncSession, order: models.FundingOrder, campaign: campaign_models.Campaign, actor: User
) -> models.FundingOrder:
    """"I have funded the pot": ask the provider whether the money arrived."""
    if order.status == models.FundingStatus.confirmed:
        return order
    if order.status not in (models.FundingStatus.awaiting_payment, models.FundingStatus.awaiting_confirmation):
        raise FundingError(f"This funding order is {order.status.value}.")
    provider = get_provider()
    try:
        state = await provider.check_collection(
            reference=order.reference, provider_reference=order.provider_reference, expected_amount=order.total_amount
        )
    except ProviderError as exc:
        raise FundingError("We couldn't reach the payment provider. Try again in a moment.", 502) from exc

    if state.received:
        await mark_confirmed(db, order, campaign, actor_id=actor.id, amount=state.amount_received)
    else:
        order.status = models.FundingStatus.awaiting_confirmation
        audit.record(db, "funding.claimed_paid", actor_id=actor.id, campaign_id=campaign.id, reference=order.reference)
    return order
