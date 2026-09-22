import uuid
from datetime import datetime

from pydantic import BaseModel

from core.money import Money

from .models import FundingMethod, FundingStatus


class FundingCreate(BaseModel):
    """Card details never come through here: card numbers go straight to the
    payment provider's hosted fields (PCI scope stays with them). This only
    records that the brand chose to pay by card."""

    method: FundingMethod = FundingMethod.bank


class FundingQuoteOut(BaseModel):
    """What the terms *would* be right now, before locking them in with
    `POST .../funding`. Server-calculated, never trusted from the client."""

    campaign_id: uuid.UUID
    pot: Money
    fee: Money
    fee_rate: float
    total: Money
    currency: str = "NGN"
    methods: list[FundingMethod]
    #: Minutes this quote should be treated as current for — the pot/fee
    #: rate rarely change, so this is informational, not an enforced expiry.
    valid_for_minutes: int = 15
    terms_version: str


class CollectionOut(BaseModel):
    bank_name: str
    account_number: str
    account_name: str


class FundingOrderOut(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    reference: str
    status: FundingStatus
    method: FundingMethod
    pot: Money
    fee: Money
    total: Money
    provider: str
    #: True when no real money is involved. The UI should say so.
    sandbox: bool
    provider_reference: str | None
    #: Send the brand here to pay (bank transfer or card). Null for the sandbox.
    checkout_url: str | None = None
    collection: CollectionOut | None
    campaign_status: str
    created_at: datetime
    confirmed_at: datetime | None
