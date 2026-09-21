import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from core.money import Money


class AdminOverview(BaseModel):
    users: dict[str, int]
    campaigns: dict[str, int]
    submissions_needing_review: int
    open_appeals: int
    payouts: dict[str, int]
    #: Earned by creators and not yet withdrawn (payable + in hold + processing).
    creator_liability: Money
    funding_awaiting_confirmation: int
    blocked_earning_accounts: int


class AdminPayoutRow(BaseModel):
    id: uuid.UUID
    reference: str
    status: str
    amount: Money
    creator_id: uuid.UUID
    creator_email: str
    creator_name: str
    provider: str
    provider_reference: str | None
    failure_reason: str | None
    initiated_at: datetime
    completed_at: datetime | None


class AdminFundingRow(BaseModel):
    id: uuid.UUID
    reference: str
    status: str
    campaign_id: uuid.UUID
    campaign_title: str
    total: Money
    provider: str
    created_at: datetime
    confirmed_at: datetime | None


class FailPayoutRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


class ConfirmFundingRequest(BaseModel):
    #: What actually arrived. Must cover the order total.
    amount_received: float = Field(gt=0)
    note: str = Field(min_length=5, max_length=300)


class VerifyBusinessRequest(BaseModel):
    verified: bool
    legal_name: str | None = Field(default=None, max_length=160)


class BlockedAccountRow(BaseModel):
    submission_id: uuid.UUID
    campaign_id: uuid.UUID
    creator_id: uuid.UUID
    reason: str
    cumulative_views: int
    accrued: Money
    last_settled_at: datetime | None


class AuditRow(BaseModel):
    id: uuid.UUID
    created_at: datetime
    kind: str
    actor_id: uuid.UUID | None
    campaign_id: uuid.UUID | None
    submission_id: uuid.UUID | None
    subject_id: uuid.UUID | None
    amount: Money | None
    data: dict


class RunResult(BaseModel):
    processed: int
