import uuid
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.money import Money
from core.platforms import Platform

from .models import AccessMode, CampaignStatus, EndCondition, PerformanceMetricType, RuleKind


SOCIAL_METRICS = {
    PerformanceMetricType.view,
    PerformanceMetricType.comment,
    PerformanceMetricType.share,
}
CONVERSION_METRICS = {
    PerformanceMetricType.visit,
    PerformanceMetricType.signup,
    PerformanceMetricType.lead,
    PerformanceMetricType.purchase,
}


class CampaignMetricIn(BaseModel):
    metric_type: PerformanceMetricType
    rate_amount: float = Field(gt=0, description="Amount paid for each unit batch")
    unit_size: int = Field(default=1, gt=0, le=1_000_000)
    min_threshold: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def sensible_units(self):
        if self.metric_type == PerformanceMetricType.view and self.unit_size < 100:
            raise ValueError("View rates must cover at least 100 views per unit.")
        if self.metric_type != PerformanceMetricType.view and self.unit_size != 1:
            raise ValueError(f"{self.metric_type.value} rates must be set per action.")
        return self


class CampaignMetricOut(CampaignMetricIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    verification_method: str
    position: int


class ConversionSetup(BaseModel):
    destination_type: Literal["website", "whatsapp"]
    destination_url: str | None = Field(default=None, max_length=2048)
    whatsapp_number: str | None = Field(default=None, max_length=24)
    attribution_window_days: int = Field(default=30, ge=1, le=90)
    attribution_model: Literal["first_touch", "last_touch"] = "last_touch"

    @field_validator("destination_url")
    @classmethod
    def valid_destination_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value.lower().startswith(("https://", "http://")):
            raise ValueError("Enter a complete website link beginning with https:// or http://.")
        if not urlsplit(value).netloc:
            raise ValueError("Enter a complete website link with a domain name.")
        return value

    @field_validator("whatsapp_number")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) < 10 or len(digits) > 15:
            raise ValueError("Enter a WhatsApp number with its country code.")
        return digits

    @model_validator(mode="after")
    def destination_matches_type(self):
        if self.destination_type == "website" and not self.destination_url:
            raise ValueError("An online store or website link is required.")
        if self.destination_type == "whatsapp" and not self.whatsapp_number:
            raise ValueError("A business WhatsApp number is required.")
        return self


class ConversionSetupDraft(BaseModel):
    """A deliberately permissive conversion setup used while autosaving.

    Campaign creation still validates the completed answer through
    ``ConversionSetup``. A draft, however, must be able to remember that a
    brand chose "website" before they have finished typing the URL.
    """

    destination_type: Literal["website", "whatsapp"] | None = None
    destination_url: str | None = Field(default=None, max_length=2048)
    whatsapp_number: str | None = Field(default=None, max_length=40)
    attribution_window_days: int = Field(default=30, ge=1, le=90)
    attribution_model: Literal["first_touch", "last_touch"] = "last_touch"

    @field_validator("destination_url", "whatsapp_number")
    @classmethod
    def keep_partial_value(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class PayoutRuleIn(BaseModel):
    rate_per_1000_views: float = Field(gt=0, description="Amount paid per 1,000 verified views")
    cap_amount: float | None = Field(
        default=None,
        gt=0,
        description="The most one creator can earn from this campaign, across all their clips",
    )
    video_cap_amount: float | None = Field(default=None, gt=0, description="The most a single clip can earn")
    max_submissions: int | None = Field(default=None, gt=0, description="The most clips one creator may submit")
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


class AssetIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=2048)
    kind: str | None = Field(default=None, max_length=40)


class AssetOut(AssetIn):
    pass


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
    access_mode: AccessMode = AccessMode.public
    assets: list[AssetIn] | None = Field(default=None, max_length=20)
    end_condition: EndCondition | None = None
    performance_metrics: list[CampaignMetricIn] = Field(default_factory=list, max_length=7)
    conversion_setup: ConversionSetup | None = None

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
        if not self.performance_metrics:
            self.performance_metrics = [
                CampaignMetricIn(
                    metric_type=PerformanceMetricType.view,
                    rate_amount=self.payout_rule.rate_per_1000_views,
                    unit_size=1000,
                    min_threshold=self.payout_rule.min_views_threshold,
                )
            ]
        kinds = [metric.metric_type for metric in self.performance_metrics]
        if len(kinds) != len(set(kinds)):
            raise ValueError("Choose each performance metric only once.")
        if any(kind in CONVERSION_METRICS for kind in kinds) and self.conversion_setup is None:
            raise ValueError("Set where customers should go for conversion tracking.")
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
    access_mode: AccessMode | None = None
    assets: list[AssetIn] | None = Field(default=None, max_length=20)
    end_condition: EndCondition | None = None
    performance_metrics: list[CampaignMetricIn] | None = Field(default=None, min_length=1, max_length=7)
    conversion_setup: ConversionSetup | None = None


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
    performance: dict[str, int] = Field(default_factory=dict)


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
    payouts_frozen: bool
    access_mode: AccessMode
    invite_code: str | None = None
    assets: list[AssetOut] = []
    end_condition: EndCondition | None = None
    video_cap: float | None = None
    max_submissions: int | None = None
    duration_days: int | None = None
    ends_at: datetime | None = None
    time_left: TimeLeft | None = None
    pot: Money
    spent: Money
    remaining: Money
    payout_rule: PayoutRuleOut | None
    performance_metrics: list[CampaignMetricOut] = Field(default_factory=list)
    conversion_setup: ConversionSetup | None = None
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
    performance: dict[str, int] = Field(default_factory=dict)


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
    access_mode: AccessMode | None = None
    assets: list[AssetIn] | None = Field(default=None, max_length=20)
    end_condition: EndCondition | None = None
    performance_metrics: list[CampaignMetricIn] | None = Field(default=None, min_length=1, max_length=7)
    conversion_setup: ConversionSetupDraft | None = None


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


class AttributionLinkCreate(BaseModel):
    submission_id: uuid.UUID | None = None


class AttributionLinkOut(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    short_code: str
    tracking_url: str
    destination_url: str
    expires_at: datetime | None


class IntegrationSecretOut(BaseModel):
    campaign_id: uuid.UUID
    secret: str
    last_four: str
    warning: str = "Copy this secret now. It will not be shown again."


class CampaignIntegrationOut(BaseModel):
    campaign_id: uuid.UUID
    configured: bool
    secret_last_four: str | None = None
    created_at: datetime | None = None
    rotated_at: datetime | None = None
    event_endpoint: str
    tracker_script_url: str
    attribution_parameter: str = "clippit_ref"
    destination_url: str | None = None
    attribution_window_days: int
    attribution_model: str
    selected_event_types: list[str] = Field(default_factory=list)
    events_received: int = 0
    last_event_at: datetime | None = None


class PerformanceEventIn(BaseModel):
    campaign_id: uuid.UUID
    event_type: PerformanceMetricType
    attribution_code: str = Field(min_length=6, max_length=16)
    source_event_id: str = Field(min_length=1, max_length=160)
    quantity: int = Field(default=1, gt=0, le=1_000_000)
    value_amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    occurred_at: datetime | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("event_type")
    @classmethod
    def conversion_event_only(cls, value: PerformanceMetricType) -> PerformanceMetricType:
        if value not in CONVERSION_METRICS:
            raise ValueError("Server events can confirm visits, signups, leads or purchases.")
        return value


class PerformanceEventOut(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    creator_id: uuid.UUID
    submission_id: uuid.UUID | None
    event_type: str
    quantity: int
    value_amount: Money | None
    currency: str | None
    verification_status: str
    occurred_at: datetime


class PerformanceMetricSummary(BaseModel):
    metric_type: str
    total: int
    approved: int
    pending: int
    earned: Money


class PerformanceSummaryOut(BaseModel):
    campaign_id: uuid.UUID
    metrics: list[PerformanceMetricSummary]
