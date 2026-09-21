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
    collection: CollectionOut | None
    campaign_status: str
    created_at: datetime
    confirmed_at: datetime | None
