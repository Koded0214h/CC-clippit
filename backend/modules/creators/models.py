"""Creators — scoped to bank details for now, the one piece Payment
Orchestration is actually blocked on. Profile fields (bio, interests —
used for campaign-notification matching per the implementation plan
§19.2) are real but not on the critical path to a payout and are
deliberately deferred rather than built speculatively.

One bank account per creator (`creator_id` is the primary key, not a
surrogate one) — a creator has one payout destination at a time.
Replacing it resets `verified` to false: changing where money goes must
always re-pass verification, otherwise a compromised account could
silently redirect a creator's future payouts. Storing here is all this
module does — resolving the account name and actually verifying it with
a payment provider is Payment Orchestration's job (owns the provider
abstraction), not this one's.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class CreatorBankAccount(Base):
    __tablename__ = "creator_bank_accounts"

    creator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    bank_code: Mapped[str] = mapped_column(String(10), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    # Filled in by Payment Orchestration once it resolves the account
    # against the provider. Null until then.
    account_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CreatorProfile(Base):
    """What a creator shows and what onboarding learned about them.
    `interests` are the content lanes used to match new campaigns to them
    (plan §19.2). One row per creator; created by onboarding."""

    __tablename__ = "creator_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_upload_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="SET NULL"), nullable=True
    )
    interests: Mapped[list[str]] = mapped_column(ARRAY(String(40)), nullable=False, server_default="{}")
    # Onboarding answers — kept for product analytics and matching, not shown.
    intended_platforms: Mapped[list[str]] = mapped_column(ARRAY(String(20)), nullable=False, server_default="{}")
    discovery_source: Mapped[str | None] = mapped_column(String(60), nullable=True)
    experience: Mapped[str | None] = mapped_column(String(80), nullable=True)
    goals: Mapped[list[str]] = mapped_column(ARRAY(String(80)), nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- resumable onboarding draft (production-api-inventory.md §C) -----
    # Autosaved per screen, ahead of `complete`. `draft_answers` holds
    # whatever subset of `CreatorOnboarding` fields have been saved so
    # far — not yet the creator's real profile, which is only written by
    # `complete`. `draft_revision` guards two tabs from clobbering each
    # other: a PATCH must send back the revision it last read.
    draft_answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    draft_step: Mapped[str | None] = mapped_column(String(40), nullable=True)
    draft_revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
