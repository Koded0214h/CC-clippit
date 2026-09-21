import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from core.money import Money

from .models import PayoutStatus


class PayoutCreate(BaseModel):
    """Withdraw. `idempotency_key` is generated once by the client per
    "Confirm withdrawal" screen, so a double tap or a retried request is one
    payout, not two."""

    amount: float = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=80)


class BankDestination(BaseModel):
    bank_code: str
    bank_name: str
    account_number_masked: str
    account_name: str


class SourceRow(BaseModel):
    campaign_title: str
    clip: str
    amount: Money


class Provenance(BaseModel):
    """"Where this money came from" on the receipt."""

    approved_clips: int
    campaigns: list[str]
    billable_views: int
    sources: list[SourceRow]


class PayoutOut(BaseModel):
    id: uuid.UUID
    reference: str
    status: PayoutStatus
    amount: Money
    fee: Money
    #: What the bank receives: amount − fee.
    net: Money
    creator_name: str
    destination: BankDestination
    provider: str
    #: True when no real money moved. The receipt must say so.
    sandbox: bool
    failure_reason: str | None
    initiated_at: datetime
    completed_at: datetime | None
    provenance: Provenance | None = None


class PayoutList(BaseModel):
    items: list[PayoutOut]
    total: int


class ResolveRequest(BaseModel):
    bank_code: str = Field(min_length=1, max_length=10)
    account_number: str = Field(min_length=10, max_length=10, pattern=r"^\d{10}$")


class ResolvedOut(BaseModel):
    account_name: str
    bank_code: str
    account_number_masked: str
