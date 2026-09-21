"""The provider-facing edge: the bank list and the signed webhook.

Nothing here decides anything about money. The webhook verifies the
provider's signature *before* reading the body, turns the event into a call
on the module that owns that money (funding, payouts), and always answers
2xx once the signature is good — a provider that gets an error retries
forever, and an event we can't match is logged, not fatal.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from integrations.payments import get_provider
from integrations.payments.base import ProviderError, WebhookKind
from modules.auth.deps import get_current_user
from modules.auth.models import User
from modules.campaigns import service as campaign_service
from modules.funding import models as funding_models
from modules.funding import service as funding_service

router = APIRouter(tags=["payments"])
logger = logging.getLogger("clippit.payments")


class BankOut(BaseModel):
    code: str
    name: str


@router.get("/banks", response_model=list[BankOut])
async def list_banks(user: User = Depends(get_current_user)):
    """Banks a creator can be paid into (the payout-account dropdown)."""
    try:
        banks = await get_provider().list_banks()
    except ProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Couldn't load the bank list. Try again shortly.") from exc
    return [BankOut(code=b.code, name=b.name) for b in banks]


@router.post("/webhooks/payments", include_in_schema=False)
async def payments_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    provider = get_provider()
    body = await request.body()
    if not provider.verify_webhook(request.headers, body):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad signature")

    event = provider.parse_webhook(body)
    if event is None:
        logger.warning("payments webhook: unreadable body")
        return {"received": True, "handled": False}

    if event.kind == WebhookKind.collection_received:
        order = await db.scalar(
            select(funding_models.FundingOrder).where(funding_models.FundingOrder.reference == event.reference)
        )
        if order is None:
            logger.warning("payments webhook: unknown funding reference %s", event.reference)
            return {"received": True, "handled": False}
        campaign = await campaign_service.resolve(db, str(order.campaign_id))
        first_time = await funding_service.mark_confirmed(db, order, campaign, actor_id=None, amount=event.amount)
        await db.commit()
        return {"received": True, "handled": True, "first_time": first_time}

    from modules.payouts import service as payout_service  # imported here: payouts depends on this package's provider edge

    handled = await payout_service.apply_transfer_event(db, event)
    await db.commit()
    return {"received": True, "handled": handled}
