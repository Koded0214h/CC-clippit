import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from modules.submissions.schemas import AppealOut, RequirementResultOut
from modules.submissions.models import VerificationStatus


class ReviewCard(BaseModel):
    """One row of the review queue."""

    id: uuid.UUID
    creator_name: str
    creator_handle: str | None
    title: str | None
    platform: str
    campaign_slug: str
    campaign_title: str
    video_url: str | None
    url: str
    confidence: float | None
    #: The one-line reason it needs a look.
    issue: str | None
    status: VerificationStatus
    is_appeal: bool
    submitted_at: datetime


class ReviewCounts(BaseModel):
    needs_review: int
    appeals: int
    resolved: int


class ReviewQueue(BaseModel):
    tab: str
    counts: ReviewCounts
    items: list[ReviewCard]


class ReviewDetail(ReviewCard):
    creator_id: uuid.UUID
    requirements: list[RequirementResultOut]
    passed: int
    total: int
    #: The requirement most in question (first `review`, else first `fail`).
    flagged_requirement: RequirementResultOut | None
    appeal: AppealOut | None
    decided_at: datetime | None
    decided_by_human: bool


class ApproveRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class CorrectionRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)
    #: The requirement that failed. Omit to flag the first one awaiting review.
    requirement_id: uuid.UUID | None = None

    @field_validator("reason")
    @classmethod
    def strip(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Say what needs correcting (at least 5 characters).")
        return value
