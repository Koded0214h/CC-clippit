import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from core.money import Money


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class OrganisationProfileUpdate(BaseModel):
    """Settings → Organisation identity + Funding contact. Every field
    optional: send only what changed."""

    name: str | None = Field(default=None, min_length=2, max_length=80)
    #: Use `GET /handles/{handle}/availability` first — this still
    #: revalidates and 409s on collision rather than trusting the client.
    slug: str | None = Field(default=None, max_length=60)
    public_profile: bool | None = None
    bio: str | None = Field(default=None, max_length=240)
    website: str | None = Field(default=None, max_length=255)
    photo_upload_id: uuid.UUID | None = None
    finance_email: EmailStr | None = None

    @field_validator("name", "bio", "website")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        return _clean(value)

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from core.handles import is_valid, normalize

        slug = normalize(value)
        if not is_valid(slug):
            raise ValueError("Slugs are 3-30 characters: lowercase letters, numbers, and underscores.")
        return slug


def _clean_list(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    seen: dict[str, None] = {}
    for value in values:
        cleaned = value.strip()[:40]
        if cleaned:
            seen[cleaned] = None
    return list(seen)[:12]


class OrganisationOnboarding(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    bio: str | None = Field(default=None, max_length=240)
    website: str | None = Field(default=None, max_length=255)
    photo_upload_id: uuid.UUID | None = None
    production_workflow: str | None = Field(default=None, max_length=60)
    team_size: str | None = Field(default=None, max_length=40)
    campaign_goal: str | None = Field(default=None, max_length=80)
    budget_range: str | None = Field(default=None, max_length=60)
    contact_name: str | None = Field(default=None, max_length=80)
    location: str | None = Field(default=None, max_length=80)
    funder_type: Literal["brand", "individual"] | None = None
    registered: bool | None = None
    content_interests: list[str] = Field(default_factory=list, max_length=12)
    viewing_interests: list[str] = Field(default_factory=list, max_length=12)
    discovery_source: str | None = Field(default=None, max_length=60)

    @field_validator("name", "bio", "website", "contact_name", "location")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        return _clean(value)

    @field_validator("content_interests", "viewing_interests")
    @classmethod
    def clean_lists(cls, value: list[str]) -> list[str]:
        return _clean_list(value) or []


class OnboardingDraftPatch(BaseModel):
    """Autosave: any subset of `OrganisationOnboarding`'s fields, plus which
    screen the person is on. See `CreatorProfile`'s draft fields for why
    `revision` exists."""

    revision: int
    step: str | None = Field(default=None, max_length=40)
    name: str | None = Field(default=None, min_length=2, max_length=80)
    bio: str | None = Field(default=None, max_length=240)
    website: str | None = Field(default=None, max_length=255)
    photo_upload_id: uuid.UUID | None = None
    production_workflow: str | None = Field(default=None, max_length=60)
    team_size: str | None = Field(default=None, max_length=40)
    campaign_goal: str | None = Field(default=None, max_length=80)
    budget_range: str | None = Field(default=None, max_length=60)
    contact_name: str | None = Field(default=None, max_length=80)
    location: str | None = Field(default=None, max_length=80)
    funder_type: Literal["brand", "individual"] | None = None
    registered: bool | None = None
    content_interests: list[str] | None = Field(default=None, max_length=12)
    viewing_interests: list[str] | None = Field(default=None, max_length=12)
    discovery_source: str | None = Field(default=None, max_length=60)

    @field_validator("name", "bio", "website", "contact_name", "location")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        return _clean(value)

    @field_validator("content_interests", "viewing_interests")
    @classmethod
    def clean_lists(cls, value: list[str] | None) -> list[str] | None:
        return _clean_list(value)


class OnboardingDraftOut(BaseModel):
    status: str
    schema_version: int = 1
    step: str | None
    revision: int
    answers: dict
    completed_at: datetime | None
    updated_at: datetime | None


class OrganisationProfileOut(BaseModel):
    user_id: uuid.UUID
    name: str
    slug: str | None = None
    public_profile: bool = True
    bio: str | None
    website: str | None
    photo_url: str | None
    finance_email: str | None
    business_legal_name: str | None
    business_verified: bool
    production_workflow: str | None
    team_size: str | None
    campaign_goal: str | None
    budget_range: str | None
    contact_name: str | None = None
    location: str | None = None
    funder_type: str | None = None
    registered: bool | None = None
    content_interests: list[str] = []
    viewing_interests: list[str] = []
    discovery_source: str | None = None
    onboarding_completed: bool = False
    updated_at: datetime


class TransactionOut(BaseModel):
    id: uuid.UUID
    kind: str  # funding | refund
    campaign_id: uuid.UUID
    campaign_title: str
    amount: Money
    fee: Money | None
    status: str
    provider: str
    provider_reference: str | None
    reference: str
    created_at: datetime
    settled_at: datetime | None


class TransactionsOut(BaseModel):
    items: list[TransactionOut]
    total: int


class PublicCampaignSummary(BaseModel):
    live_campaigns: int
    completed_campaigns: int


class PublicOrganisationProfileOut(BaseModel):
    slug: str
    name: str
    photo_url: str | None
    bio: str | None
    website: str | None
    business_verified: bool
    campaigns: PublicCampaignSummary
