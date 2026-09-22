import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.money import Money
from core.platforms import Platform

from .models import AppealStatus, RequirementVerdict, SubmissionStatus, VerificationStatus


class SubmissionCreate(BaseModel):
    campaign_id: uuid.UUID
    platform: Platform
    url: str = Field(min_length=1, max_length=2048)
    title: str | None = Field(default=None, max_length=200)
    #: The original file, uploaded first via POST /uploads/videos.
    video_upload_id: uuid.UUID | None = None

    @field_validator("url", "title")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class ResubmitIn(BaseModel):
    platform: Platform
    url: str = Field(min_length=1, max_length=2048)
    title: str | None = Field(default=None, max_length=200)
    video_upload_id: uuid.UUID | None = None

    @field_validator("url", "title")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class AppealCreate(BaseModel):
    reason: str = Field(min_length=20, max_length=600)
    evidence_upload_id: uuid.UUID | None = None

    @field_validator("reason")
    @classmethod
    def strip(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 20:
            raise ValueError("Explain what the check missed in at least 20 characters.")
        return value


class RequirementResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_id: uuid.UUID | None
    kind: str
    text: str
    position: int
    verdict: RequirementVerdict
    note: str | None


class AppealOut(BaseModel):
    id: uuid.UUID
    status: AppealStatus
    reason: str
    evidence_url: str | None
    decision_note: str | None
    created_at: datetime
    decided_at: datetime | None


class VerificationStep(BaseModel):
    """One line of the "Checking your clip" screen."""

    key: str
    title: str
    detail: str
    #: done | active | pending | failed
    state: str


class VerificationOut(BaseModel):
    status: VerificationStatus
    #: 0-100 when a verifier produced one; null for a plain human review.
    confidence: float | None
    summary: str | None
    verdict_at: datetime | None
    #: True when a person (not an automated check) decided.
    decided_by_human: bool
    requirements: list[RequirementResultOut]
    passed: int
    total: int
    #: The requirement a rejection is about, for the "Correction needed" screen.
    failed_requirement: RequirementResultOut | None
    steps: list[VerificationStep]
    appeal: AppealOut | None


class SubmissionCampaignOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    brand_name: str | None


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    creator_id: uuid.UUID
    platform: Platform
    url: str
    title: str | None = None
    video_url: str | None = None
    status: SubmissionStatus
    rejection_code: str | None
    rejection_message: str | None
    created_at: datetime
    updated_at: datetime
    campaign: SubmissionCampaignOut | None = None
    verification: VerificationOut | None = None
    resubmitted_from_id: uuid.UUID | None = None


class SubmissionEarningsOut(BaseModel):
    """"Accrued so far" and "becomes payable" on the approved screen."""

    submission_id: uuid.UUID
    verified_views: int
    accrued: Money
    #: When the earliest not-yet-payable amount clears the hold; null if
    #: nothing is held.
    next_payable_at: datetime | None
    payable_now: Money
