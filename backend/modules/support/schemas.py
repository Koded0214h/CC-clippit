import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import TicketPriority, TicketStatus


class TicketCreate(BaseModel):
    category: str = Field(min_length=1, max_length=60)
    subject: str = Field(min_length=2, max_length=200)
    message: str = Field(min_length=1, max_length=5000)
    resource_type: str | None = Field(default=None, max_length=40)
    resource_id: uuid.UUID | None = None
    attachment_upload_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)

    @field_validator("subject", "message")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    attachment_upload_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)

    @field_validator("body")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author_id: uuid.UUID
    from_admin: bool
    body: str
    attachment_upload_ids: list[uuid.UUID]
    created_at: datetime


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author_id: uuid.UUID
    body: str
    created_at: datetime


class TicketOut(BaseModel):
    id: uuid.UUID
    category: str
    subject: str
    status: TicketStatus
    priority: TicketPriority
    resource_type: str | None
    resource_id: uuid.UUID | None
    unread_count: int
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class TicketDetailOut(TicketOut):
    messages: list[MessageOut]


class TicketAdminOut(TicketDetailOut):
    """The operator view: the thread plus internal notes and safe customer
    context — never returned from the customer-facing endpoint."""

    notes: list[NoteOut]
    customer_email: EmailStr
    customer_role: str
    assignee_id: uuid.UUID | None


class TicketPatch(BaseModel):
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    category: str | None = Field(default=None, max_length=60)
    assignee_id: uuid.UUID | None = None
