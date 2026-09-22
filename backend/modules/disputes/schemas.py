import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.money import Money

from .models import DisputeResolution, DisputeStatus, DisputeType


class DisputeCreate(BaseModel):
    type: DisputeType
    resource_id: uuid.UUID
    reason: str = Field(min_length=20, max_length=2000)

    @field_validator("reason")
    @classmethod
    def strip(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 20:
            raise ValueError("Explain the dispute in at least 20 characters.")
        return value


class DisputeMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    evidence_upload_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)

    @field_validator("body")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()


class DisputeMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author_id: uuid.UUID
    from_admin: bool
    body: str
    evidence_upload_ids: list[uuid.UUID]
    created_at: datetime


class DisputeOut(BaseModel):
    id: uuid.UUID
    type: DisputeType
    resource_id: uuid.UUID
    reason: str
    status: DisputeStatus
    amount_at_risk: Money | None
    deadline_at: datetime
    resolution: DisputeResolution | None
    resolution_note: str | None
    unread_count: int
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class DisputeDetailOut(DisputeOut):
    messages: list[DisputeMessageOut]


class DisputeAdminOut(DisputeDetailOut):
    assignee_id: uuid.UUID | None
    customer_role: str


class DisputePatch(BaseModel):
    assignee_id: uuid.UUID | None = None
    status: DisputeStatus | None = None


class DisputeResolve(BaseModel):
    resolution: DisputeResolution
    note: str = Field(min_length=1, max_length=2000)
