from datetime import datetime

from pydantic import BaseModel, Field


class LegalDocumentOut(BaseModel):
    slug: str
    version: str
    title: str
    effective_date: str
    body: str


class AcceptanceIn(BaseModel):
    slug: str = Field(max_length=60)
    version: str = Field(max_length=20)
    action: str = Field(max_length=60)


class AcceptanceOut(BaseModel):
    slug: str
    version: str
    action: str
    accepted_at: datetime


class MyAcceptancesOut(BaseModel):
    accepted: list[AcceptanceOut]
    #: Documents this account has never accepted at their current version.
    newly_required: list[str]
