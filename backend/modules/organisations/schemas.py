import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class OrganisationProfileUpdate(BaseModel):
    """Settings → Organisation identity + Funding contact. Every field
    optional: send only what changed."""

    name: str | None = Field(default=None, min_length=2, max_length=80)
    bio: str | None = Field(default=None, max_length=240)
    website: str | None = Field(default=None, max_length=255)
    photo_upload_id: uuid.UUID | None = None
    finance_email: EmailStr | None = None

    @field_validator("name", "bio", "website")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        return _clean(value)


class OrganisationOnboarding(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    bio: str | None = Field(default=None, max_length=240)
    photo_upload_id: uuid.UUID | None = None
    production_workflow: str | None = Field(default=None, max_length=60)
    team_size: str | None = Field(default=None, max_length=40)
    campaign_goal: str | None = Field(default=None, max_length=80)
    budget_range: str | None = Field(default=None, max_length=60)

    @field_validator("name", "bio")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        return _clean(value)


class OrganisationProfileOut(BaseModel):
    user_id: uuid.UUID
    name: str
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
    updated_at: datetime
