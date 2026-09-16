import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.platforms import Platform

from .models import SubmissionStatus


class SubmissionCreate(BaseModel):
    campaign_id: uuid.UUID
    platform: Platform
    url: str = Field(min_length=1, max_length=2048)


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    creator_id: uuid.UUID
    platform: Platform
    url: str
    status: SubmissionStatus
    rejection_code: str | None
    rejection_message: str | None
    created_at: datetime
    updated_at: datetime
