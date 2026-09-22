import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import ReportResolution, ReportStatus, ReportTargetType


class ReportCreate(BaseModel):
    target_type: ReportTargetType
    target_id: uuid.UUID
    reason: str = Field(min_length=2, max_length=60)
    details: str | None = Field(default=None, max_length=2000)
    evidence_upload_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)

    @field_validator("reason", "details")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_type: ReportTargetType
    target_id: uuid.UUID
    reason: str
    status: ReportStatus
    created_at: datetime


class ReportAdminOut(ReportOut):
    reporter_id: uuid.UUID
    details: str | None
    evidence_upload_ids: list[uuid.UUID]
    resolution: ReportResolution | None
    resolution_note: str | None
    resolved_at: datetime | None


class ReportResolve(BaseModel):
    resolution: ReportResolution
    note: str = Field(min_length=1, max_length=2000)
