import uuid
from datetime import datetime

from pydantic import BaseModel

from core.money import Money


class RefundIn(BaseModel):
    reason: str


class RefundOut(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    amount: Money
    status: str
    reason: str
    provider: str
    sandbox: bool
    provider_reference: str | None
    failure_reason: str | None
    created_at: datetime
    processed_at: datetime | None
