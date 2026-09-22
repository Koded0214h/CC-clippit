import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.money import Money
from core.platforms import Platform

from .models import CampaignStatus, RuleKind


class PayoutRuleIn(BaseModel):
    rate_per_1000_views: float = Field(gt=0, description="Amount paid per 1,000 verified views")
    cap_amount: float | None = Field(
        default=None,
        gt=0,
        description="The most one creator can earn from this campaign, across all their clips",
    )
    min_views_threshold: int = Field(default=1000, ge=0, description="Views required before anything is owed")


class PayoutRuleOut(PayoutRuleIn):
    model_config = ConfigDict(from_attributes=True)


class RuleIn(BaseModel):
    kind: RuleKind
    text: str = Field(min_length=5, max_length=300)

    @field_validator("text")
    @classmethod
    def strip(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("A requirement needs at least 5 characters.")
        return value


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: RuleKind
    text: str
    position: int


class RulesReplace(BaseModel):
    rules: list[RuleIn] = Field(max_length=20)


class CampaignCreate(BaseModel):
    """`pot` (what the brand budgets) and `expected_views` (what that buys)
    are two views of one number. Send either; if both are sent, `pot` wins and
    `expected_views` is recomputed from it at the payout rate."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    tagline: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=40)
    source_link: str | None = Field(default=None, max_length=500)
    platforms: list[Platform] = Field(min_length=1)
    pot: float | None = Field(default=None, gt=0)
    expected_views: int | None = Field(default=None, gt=0)
    payout_rule: PayoutRuleIn
    duration_days: int | None = Field(default=None, ge=1, le=90)
    cover_image_upload_id: uuid.UUID | None = None
    rules: list[RuleIn] = Field(default_factory=list, max_length=20)

    @field_validator("platforms")
    @classmethod
    def dedupe_platforms(cls, value: list[Platform]) -> list[Platform]:
        return list(dict.fromkeys(value))

    @field_validator("title", "description", "tagline", "category", "source_link")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def needs_a_budget(self):
        if self.pot is None and self.expected_views is None:
            raise ValueError("Set either pot or expected_views.")
        return self


class CampaignUpdate(BaseModel):
    """Only accepted while the campaign is still `draft` (enforced in the
    router, not here) — once a campaign is funded, creators are submitting
    against its promised terms, and admin is the only role that can still
    correct it."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    tagline: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=40)
    source_link: str | None = Field(default=None, max_length=500)
    expected_views: int | None = Field(default=None, gt=0)
    pot: float | None = Field(default=None, gt=0)
    platforms: list[Platform] | None = Field(default=None, min_length=1)
    duration_days: int | None = Field(default=None, ge=1, le=90)
    cover_image_upload_id: uuid.UUID | None = None


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


class BrandOut(BaseModel):
    id: uuid.UUID
    name: str
    photo_url: str | None = None
    verified: bool = False


class TimeLeft(BaseModel):
    days: int
    hours: int
    ended: bool


class CampaignMetrics(BaseModel):
    """What the brand's dashboards show. Only the campaign's owner (and
    admin) receive it."""

    verified_views: int
    submissions: int
    approved: int
    review: int
    checking: int
    rejected: int
    earned: Money


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    event_manager_id: uuid.UUID
    brand: BrandOut | None = None
    title: str
    tagline: str | None = None
    description: str
    category: str | None = None
    source_link: str | None = None
    cover_image_url: str | None = None
    expected_views: int
    platforms: list[Platform]
    status: CampaignStatus
    #: The brand-facing word for `status`: Funding / Draft / Live / Completed.
    phase: str
    accepting_entries: bool
    duration_days: int | None = None
    ends_at: datetime | None = None
    time_left: TimeLeft | None = None
    pot: Money
    spent: Money
    remaining: Money
    payout_rule: PayoutRuleOut | None
    rules: list[RuleOut] = []
    #: Creators only: Open / Closing soon / Joined.
    feed_status: str | None = None
    joined: bool | None = None
    metrics: CampaignMetrics | None = None
    created_at: datetime
    updated_at: datetime


class CampaignStats(BaseModel):
    campaign_id: uuid.UUID
    phase: str
    accepting_entries: bool
    pot: Money
    spent: Money
    remaining: Money
    percent_remaining: float
    verified_views: int
    views_last_24h: int
    submissions: int
    approved: int
    review: int
    checking: int
    rejected: int
    time_left: TimeLeft | None
    last_reading_at: datetime | None


class CampaignSubmissionRow(BaseModel):
    id: uuid.UUID
    creator_id: uuid.UUID
    creator_name: str
    creator_handle: str | None
    title: str | None
    platform: str
    url: str
    verified_views: int
    earned: Money
    #: Earning / Review / Checking / Rejected / Withdrawn.
    state: str
    submitted_at: datetime


class BrandOverviewOut(BaseModel):
    organisation_name: str
    pending_reviews: int
    live_campaigns: int
    draft_campaigns: int
    completed_campaigns: int
    total_pot: Money
    total_spent: Money
    views_last_24h: int
    earnings_last_24h: Money
    #: Money paid to creators that doesn't trace back to a verified reading.
    #: Zero by construction — every accrual carries the snapshot it came from.
    unmatched_spend: Money
    featured: CampaignOut | None


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    joined_at: datetime
    left_at: datetime | None = None


class MyCampaignRow(BaseModel):
    """One row of `GET /creators/me/campaigns` — the campaign plus this
    creator's own relationship to it, distinct from the campaign's own
    status."""

    campaign: CampaignOut
    #: joined | submitted | active | completed | left — see the router.
    membership_status: str
    joined_at: datetime | None = None
    left_at: datetime | None = None
    submission_id: uuid.UUID | None = None
    submission_status: str | None = None


# --- campaign studio drafts ---------------------------------------------------


class CampaignDraftPatch(BaseModel):
    """Autosave: any subset of `CampaignCreate`'s fields, screen by screen,
    plus which step the builder is on. `revision` must be the value last
    read from `GET` — see the same pattern on onboarding drafts."""

    revision: int
    step: str | None = Field(default=None, max_length=40)
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    tagline: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=40)
    source_link: str | None = Field(default=None, max_length=500)
    platforms: list[Platform] | None = None
    pot: float | None = Field(default=None, gt=0)
    expected_views: int | None = Field(default=None, gt=0)
    payout_rule: PayoutRuleIn | None = None
    duration_days: int | None = Field(default=None, ge=1, le=90)
    cover_image_upload_id: uuid.UUID | None = None
    rules: list[RuleIn] | None = Field(default=None, max_length=20)


class CampaignDraftOut(BaseModel):
    id: uuid.UUID
    schema_version: int
    #: not_started | in_progress | finalized
    status: str
    step: str | None
    revision: int
    answers: dict
    #: What's still missing before `finalize` would succeed — field name to
    #: a short reason, so the builder can flag exactly the blocked screen.
    blockers: dict[str, str]
    finalized_campaign_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class CampaignDraftFinalizeOut(BaseModel):
    campaign_id: uuid.UUID
    campaign_slug: str
    next_route: str
