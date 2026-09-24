"""The organisation behind an `organisation`-role user: the identity
creators see on its campaigns, and the funding contact used for receipts.

`business_verified` is set only by an admin after checking the business —
never by the organisation itself — because campaign funding trust rests on
it (the settings screen shows it as a verified-funder badge).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class OrganisationProfile(Base):
    __tablename__ = "organisation_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    #: The public slug behind `/profiles/organisations/{slug}`. Null until
    #: set — no public profile page exists before then.
    slug: Mapped[str | None] = mapped_column(String(60), unique=True, nullable=True)
    public_profile: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_upload_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="SET NULL"), nullable=True
    )
    finance_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_legal_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    business_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # Onboarding answers — not shown on the public identity.
    production_workflow: Mapped[str | None] = mapped_column(String(60), nullable=True)
    team_size: Mapped[str | None] = mapped_column(String(40), nullable=True)
    campaign_goal: Mapped[str | None] = mapped_column(String(80), nullable=True)
    budget_range: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- resumable onboarding draft — see the same fields on CreatorProfile.
    draft_answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    draft_step: Mapped[str | None] = mapped_column(String(40), nullable=True)
    draft_revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class OrganisationBankAccount(Base):
    """The brand's own withdrawal destination — see `CreatorBankAccount`'s
    docstring for why this is a one-account-at-a-time, re-verify-on-change
    model. PRD V1's brand wallet withdrawal (7% fee) pays out here."""

    __tablename__ = "organisation_bank_accounts"

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    bank_code: Mapped[str] = mapped_column(String(10), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    account_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
