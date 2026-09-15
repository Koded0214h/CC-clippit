"""Campaign Management — owned by Koded's core-backend domain (see
architecture/intelligence-contracts.md §1, decision D1).

Unlike the Adam/Koded boundary, `campaigns` and `users` are both mine, so
`event_manager_id` is a real foreign key rather than a bare UUID — there's
no independent-migrations reason to avoid it here the way Intelligence
avoids FKs into this module's tables.

`platforms` is a Postgres array of plain strings, validated against
`core.platforms.Platform` at the schema layer rather than a native enum
type — the same reason Intelligence's tables do this (see D5): a second
native enum type constraining the same values as auth's `platform` type
would just be another thing to keep in sync by hand.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    closed = "closed"


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (CheckConstraint("expected_views > 0", name="ck_campaigns_expected_views_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_manager_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    expected_views: Mapped[int] = mapped_column(Integer, nullable=False)
    # Values from core.platforms.Platform — see the module docstring.
    platforms: Mapped[list[str]] = mapped_column(ARRAY(String(20)), nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status"), nullable=False, server_default=CampaignStatus.draft.value
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    payout_rule: Mapped["CampaignPayoutRule"] = relationship(
        back_populates="campaign", uselist=False, cascade="all, delete-orphan"
    )


class CampaignPayoutRule(Base):
    """One rule per campaign today. A separate table (rather than columns
    on Campaign) because a campaign with tiered or per-platform rates is a
    real near-term requirement, not hypothetical — this is where that
    grows without another migration touching `campaigns` itself."""

    __tablename__ = "campaign_payout_rules"
    __table_args__ = (
        CheckConstraint("rate_per_1000_views > 0", name="ck_payout_rate_positive"),
        CheckConstraint("cap_amount IS NULL OR cap_amount > 0", name="ck_payout_cap_positive"),
        CheckConstraint("min_views_threshold >= 0", name="ck_payout_min_views_nonnegative"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True
    )
    rate_per_1000_views: Mapped[float] = mapped_column(Float, nullable=False)
    cap_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_views_threshold: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1000")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="payout_rule")
