import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

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


# --- users ---------------------------------------------------------------------


class AdminUserRow(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    email_verified: bool
    onboarding_completed: bool
    suspended: bool
    created_at: datetime


class AdminUserDetail(AdminUserRow):
    active_sessions: int
    connected_platforms: int
    #: Creator: earnings balances. Organisation: campaign/funding counts.
    #: Empty for an admin account.
    money_summary: dict
    suspension_scopes: list[str]
    suspension_reason: str | None
    suspension_expires_at: datetime | None
    recent_audit: list[AuditRow]


class SuspendUserRequest(BaseModel):
    scopes: list[str] = Field(min_length=1, description='Any of "access", "funding", "earning"')
    reason: str = Field(min_length=5, max_length=500)
    duration_days: int | None = Field(default=None, gt=0, le=365)

    @field_validator("scopes")
    @classmethod
    def known_scopes(cls, value: list[str]) -> list[str]:
        allowed = {"access", "funding", "earning"}
        bad = set(value) - allowed
        if bad:
            raise ValueError(f"Unknown suspension scope(s): {sorted(bad)}")
        return sorted(set(value))


# --- submissions / trust --------------------------------------------------------


class AdminSubmissionRow(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    campaign_title: str
    creator_id: uuid.UUID
    creator_name: str
    platform: str
    status: str
    verification_status: str
    flagged: bool
    cumulative_views: int
    accrued: Money
    created_at: datetime


class AdminSubmissionDetail(AdminSubmissionRow):
    url: str
    verification_summary: str | None
    trust: dict | None
    admin_trust_override: bool | None
    hold_active: bool
    hold_reason: str | None


class TrustDecisionRequest(BaseModel):
    note: str = Field(min_length=5, max_length=1000)


# --- campaigns -------------------------------------------------------------------


class AdminCampaignRow(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    organisation_id: uuid.UUID
    organisation_name: str
    status: str
    pot: Money
    spent: Money
    needs_review: int
    created_at: datetime


class AdminCampaignDetail(AdminCampaignRow):
    platforms: list[str]
    duration_days: int | None
    ends_at: datetime | None
    submissions: int


class EmergencyActionRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


# --- earnings ----------------------------------------------------------------


class AdminEarningEntryRow(BaseModel):
    id: uuid.UUID
    submission_id: uuid.UUID
    campaign_id: uuid.UUID
    creator_id: uuid.UUID
    amount: Money
    billable_views: int
    thousands: int
    payable_at: datetime
    accrued_at: datetime
    on_hold: bool
    trust_blocked: bool


class HoldRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


# --- ledger --------------------------------------------------------------------


class AdminLedgerRow(BaseModel):
    id: uuid.UUID
    kind: str  # funding | refund | payout
    organisation_id: uuid.UUID | None
    creator_id: uuid.UUID | None
    campaign_id: uuid.UUID | None
    amount: Money
    status: str
    provider: str
    provider_reference: str | None
    reference: str
    created_at: datetime
    settled_at: datetime | None
