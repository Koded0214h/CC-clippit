import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BankAccountIn(BaseModel):
    bank_code: str = Field(min_length=1, max_length=10)
    bank_name: str = Field(min_length=1, max_length=120)
    account_number: str = Field(min_length=4, max_length=20)

    @field_validator("account_number")
    @classmethod
    def digits_only(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("Account number must contain digits only")
        return value


class BankAccountOut(BaseModel):
    creator_id: uuid.UUID
    bank_code: str
    bank_name: str
    account_number_masked: str
    account_name: str | None
    verified: bool
    verified_at: datetime | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=False)

    @classmethod
    def from_model(cls, account) -> "BankAccountOut":
        digits = account.account_number
        masked = "*" * max(len(digits) - 4, 0) + digits[-4:]
        return cls(
            creator_id=account.creator_id,
            bank_code=account.bank_code,
            bank_name=account.bank_name,
            account_number_masked=masked,
            account_name=account.account_name,
            verified=account.verified,
            verified_at=account.verified_at,
            updated_at=account.updated_at,
        )
