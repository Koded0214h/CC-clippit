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
