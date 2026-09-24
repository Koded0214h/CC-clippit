import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.money import Money

from .models import WithdrawalStatus


class BrandWalletOut(BaseModel):
    role: str = "organisation"
    available: Money
    reserved: Money
    withdrawn_all_time: Money
    min_withdrawal: int
    withdrawal_fee_rate: float


class CreatorWalletOut(BaseModel):
    """Same shape `GET /earnings/summary` already returns — this is a
    thin, PRD-naming wrapper so `GET /wallet` has one contract for both
    roles rather than the frontend branching on two different endpoints."""

    role: str = "creator"
    held: Money
    available: Money
    processing: Money
    paid_all_time: Money
    min_withdrawal: int
    withdrawal_fee_rate: float


class OrgBankAccountIn(BaseModel):
    bank_code: str = Field(min_length=1, max_length=10)
    bank_name: str = Field(min_length=1, max_length=120)
    account_number: str = Field(min_length=6, max_length=20)

    @field_validator("account_number")
    @classmethod
    def digits_only(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Account number must contain digits only.")
        return v


class OrgBankAccountOut(BaseModel):
    organisation_id: uuid.UUID
    bank_code: str
    bank_name: str
    account_number_masked: str
    account_name: str | None
    verified: bool
    verified_at: datetime | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=False)

    @classmethod
    def from_model(cls, account) -> "OrgBankAccountOut":
        digits = account.account_number
        masked = "*" * max(len(digits) - 4, 0) + digits[-4:]
        return cls(
            organisation_id=account.organisation_id, bank_code=account.bank_code, bank_name=account.bank_name,
            account_number_masked=masked, account_name=account.account_name, verified=account.verified,
            verified_at=account.verified_at, updated_at=account.updated_at,
        )


class WithdrawalCreate(BaseModel):
    amount: float = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=80)


class WithdrawalQuoteOut(BaseModel):
    amount: Money
    fee: Money
    net_amount: Money
    currency: str = "NGN"


class WithdrawalDestination(BaseModel):
    bank_code: str
    bank_name: str
    account_number_masked: str
    account_name: str


class WithdrawalOut(BaseModel):
    id: uuid.UUID
    reference: str
    status: WithdrawalStatus
    amount: Money
    fee: Money
    net: Money
    organisation_name: str
    destination: WithdrawalDestination
    provider: str
    sandbox: bool
    failure_reason: str | None
    initiated_at: datetime
    completed_at: datetime | None
