import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.money import Money
from core.platforms import Platform
from modules.campaigns.schemas import CampaignOut
from modules.earnings.schemas import EarningsSummary


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


def _strip_list(values: list[str], limit: int, size: int) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        cleaned = value.strip()[:size]
        if cleaned:
            seen[cleaned] = None
    return list(seen)[:limit]


class CreatorProfileUpdate(BaseModel):
    """Settings → Profile. Send only what changed."""

    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    #: Use `GET /handles/{handle}/availability` first — this still
    #: revalidates and 409s on collision rather than trusting the client.
    handle: str | None = Field(default=None, max_length=30)
    public_profile: bool | None = None
    bio: str | None = Field(default=None, max_length=240)
    photo_upload_id: uuid.UUID | None = None
    interests: list[str] | None = Field(default=None, max_length=12)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    location: str | None = Field(default=None, max_length=80)

    @field_validator("country")
    @classmethod
    def upper_country(cls, value: str | None) -> str | None:
        return value.upper() if value else None

    @field_validator("display_name", "bio", "location")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("handle")
    @classmethod
    def normalize_handle(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from core.handles import is_valid, normalize

        handle = normalize(value)
        if not is_valid(handle):
            raise ValueError("Handles are 3-30 characters: lowercase letters, numbers, and underscores.")
        return handle

    @field_validator("interests")
    @classmethod
    def clean_interests(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _strip_list(value, 12, 40)


class CreatorOnboarding(BaseModel):
    """`/onboarding/creator`: name, content lanes, platforms, and the
    discovery / experience / goals questions."""

    display_name: str = Field(min_length=2, max_length=80)
    interests: list[str] = Field(min_length=1, max_length=12)
    platforms: list[Platform] = Field(default_factory=list)
    photo_upload_id: uuid.UUID | None = None
    discovery_source: str | None = Field(default=None, max_length=60)
    experience: str | None = Field(default=None, max_length=80)
    goals: list[str] = Field(default_factory=list, max_length=8)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    location: str | None = Field(default=None, max_length=80)
    viewing_interests: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("country")
    @classmethod
    def upper_country(cls, value: str | None) -> str | None:
        return value.upper() if value else None

    @field_validator("display_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("location")
    @classmethod
    def strip_location(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    @field_validator("viewing_interests")
    @classmethod
    def clean_viewing(cls, value: list[str]) -> list[str]:
        return _strip_list(value, 12, 40)

    @field_validator("interests")
    @classmethod
    def clean_interests(cls, value: list[str]) -> list[str]:
        cleaned = _strip_list(value, 12, 40)
        if not cleaned:
            raise ValueError("Pick at least one content lane.")
        return cleaned

    @field_validator("goals")
    @classmethod
    def clean_goals(cls, value: list[str]) -> list[str]:
        return _strip_list(value, 8, 80)


class CreatorProfileOut(BaseModel):
    user_id: uuid.UUID
    display_name: str
    handle: str | None = None
    public_profile: bool = True
    bio: str | None
    photo_url: str | None
    interests: list[str]
    platforms: list[Platform]
    discovery_source: str | None
    experience: str | None
    goals: list[str]
    country: str | None = None
    location: str | None = None
    viewing_interests: list[str] = []
    onboarding_completed: bool
    updated_at: datetime


class PublicCreatorStats(BaseModel):
    approved_clips: int
    verified_views: int


class PublicCreatorWork(BaseModel):
    campaign_title: str
    campaign_slug: str
    brand_name: str | None
    platform: Platform
    submitted_at: datetime


class PublicCreatorProfileOut(BaseModel):
    handle: str
    display_name: str
    photo_url: str | None
    bio: str | None
    interests: list[str]
    stats: PublicCreatorStats
    recent_work: list[PublicCreatorWork]


class ClipRow(BaseModel):
    id: uuid.UUID
    title: str | None
    platform: str
    campaign_slug: str
    campaign_title: str
    brand: str | None
    #: approved | checking | needs_attention | appealed | withdrawn
    status: str
    label: str
    verified_views: int
    earned: Money
    #: The frontend page that shows this clip's verdict.
    link: str
    submitted_at: datetime


class ClipsOut(BaseModel):
    active_clips: int
    verified_views: int
    total_earned: Money
    items: list[ClipRow]


class ConnectedAccountOut(BaseModel):
    platform: Platform
    #: Clippit can start a connection for this platform. False when its
    #: OAuth app credentials aren't set on the server, or it isn't in V1.
    connectable: bool
    connected: bool
    handle: str | None
    display_name: str | None
    connected_at: datetime | None
    last_checked_at: datetime | None


class OnboardingDraftPatch(BaseModel):
    """Autosave: any subset of `CreatorOnboarding`'s fields, plus which
    screen the person is on. `revision` is the value the client last read
    from `GET`; a stale one means another tab moved faster and the client
    should re-fetch rather than overwrite it."""

    revision: int
    step: str | None = Field(default=None, max_length=40)
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    interests: list[str] | None = Field(default=None, max_length=12)
    platforms: list[Platform] | None = None
    photo_upload_id: uuid.UUID | None = None
    discovery_source: str | None = Field(default=None, max_length=60)
    experience: str | None = Field(default=None, max_length=80)
    goals: list[str] | None = Field(default=None, max_length=8)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    location: str | None = Field(default=None, max_length=80)
    viewing_interests: list[str] | None = Field(default=None, max_length=12)


class OnboardingDraftOut(BaseModel):
    #: not_started | in_progress | completed
    status: str
    schema_version: int = 1
    step: str | None
    revision: int
    answers: dict
    completed_at: datetime | None
    updated_at: datetime | None


class CreatorOverview(BaseModel):
    """The dashboard home in one call."""

    closing_soon: CampaignOut | None
    #: Live campaigns created in the last 7 days that match the creator's
    #: content lanes and that they haven't joined.
    new_matches: int
    earnings: EarningsSummary
