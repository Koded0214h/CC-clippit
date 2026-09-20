import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.platforms import Platform

from .models import CampaignStatus


class PayoutRuleIn(BaseModel):
    rate_per_1000_views: float = Field(gt=0, description="Amount paid per 1,000 verified views")
    cap_amount: float | None = Field(default=None, gt=0, description="Max total payout for one submission")
    min_views_threshold: int = Field(default=1000, ge=0, description="Views required before anything is owed")


class PayoutRuleOut(PayoutRuleIn):
    model_config = ConfigDict(from_attributes=True)


class CampaignCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    expected_views: int = Field(gt=0)
    platforms: list[Platform] = Field(min_length=1)
    payout_rule: PayoutRuleIn

    @field_validator("platforms")
    @classmethod
    def dedupe_platforms(cls, value: list[Platform]) -> list[Platform]:
        seen = list(dict.fromkeys(value))
        return seen


class CampaignUpdate(BaseModel):
    """Only accepted while the campaign is still `draft` (enforced in the
    router, not here) — once a campaign is active, creators are submitting
    against its promised terms, and admin is the only role that can still
    correct it."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    expected_views: int | None = Field(default=None, gt=0)
    platforms: list[Platform] | None = Field(default=None, min_length=1)


class PoolOut(BaseModel):
    """Read-only view of promised spend vs what current views would cost.

    Units match `rate_per_1000_views`. This is not a transfer and not a
    ledger balance — see `pool.py`.
    """

    campaign_id: uuid.UUID
    pot: float
    allocated: float
    remaining: float
    percent_given: float
    percent_remaining: float
    submissions_counted: int


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_manager_id: uuid.UUID
    title: str
    description: str
    expected_views: int
    platforms: list[Platform]
    status: CampaignStatus
    payout_rule: PayoutRuleOut | None
    created_at: datetime
    updated_at: datetime
