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
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from core.money import MoneyColumn


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    #: A funding order exists and the pot has not been confirmed yet. The
    #: terms are locked; cancelling the order returns the campaign to draft.
    pending_funding = "pending_funding"
    active = "active"
    closed = "closed"


class CloseReason(str, enum.Enum):
    manual = "manual"
    deadline = "deadline"
    pot_empty = "pot_empty"
    admin = "admin"


class AccessMode(str, enum.Enum):
    public = "public"
    invite = "invite"


class EndCondition(str, enum.Enum):
    """Which of the two things stops the campaign first — both are always
    enforced (see `service.is_open_for_entries`/settlement's pot check);
    this only records which one the brand picked as the *primary* stop, for
    display (PRD V1's campaign builder asks for one)."""

    duration = "duration"
    budget = "budget"


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
    # URL-safe identifier the frontend routes on (/dashboard/campaigns/<slug>).
    slug: Mapped[str] = mapped_column(String(96), nullable=False, unique=True, index=True)
    tagline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    source_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_image_upload_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="SET NULL"), nullable=True
    )
    #: The promised budget. Funded in full before the campaign opens; the
    #: hard ceiling on what creators can be paid (plan §25).
    pot_amount: Mapped[Decimal] = mapped_column(MoneyColumn, nullable=False, server_default="0")
    #: How long the campaign runs once it opens.
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_reason: Mapped[CloseReason | None] = mapped_column(Enum(CloseReason, name="close_reason"), nullable=True)
    #: "Pause new entries": existing submissions keep earning.
    accepting_entries: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    #: "Full freeze": also stops accrual on already-approved submissions
    #: (see earnings.service.settle_submission) until resumed. Distinct
    #: from `accepting_entries` — a brand can freeze payouts without also
    #: closing the door on new joins, or vice versa.
    payouts_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    access_mode: Mapped[AccessMode] = mapped_column(
        Enum(AccessMode, name="campaign_access_mode"), nullable=False, server_default=AccessMode.public.value
    )
    #: Set only when `access_mode` is `invite`; required to join then (see
    #: `service.join_campaign`). Never required to view the campaign itself.
    invite_code: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    #: Reference files/links for creators — moodboards, sounds, briefs — not
    #: the cover image (that's `cover_image_upload_id`) or the video brief
    #: rules (those are `CampaignRule`). Each item: {name, url, kind}.
    assets: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    end_condition: Mapped[EndCondition | None] = mapped_column(
        Enum(EndCondition, name="campaign_end_condition"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    payout_rule: Mapped["CampaignPayoutRule"] = relationship(
        back_populates="campaign", uselist=False, cascade="all, delete-orphan"
    )
    rules: Mapped[list["CampaignRule"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", order_by="CampaignRule.position"
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
        CheckConstraint("video_cap_amount IS NULL OR video_cap_amount > 0", name="ck_payout_video_cap_positive"),
        CheckConstraint("max_submissions IS NULL OR max_submissions > 0", name="ck_payout_max_submissions_positive"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True
    )
    rate_per_1000_views: Mapped[float] = mapped_column(Float, nullable=False)
    #: The most one creator can earn from this campaign, across all their clips.
    cap_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    #: The most a *single* clip can earn, regardless of its own views.
    video_cap_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    #: The most clips one creator may submit to this campaign.
    max_submissions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_views_threshold: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1000")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="payout_rule")


class RuleKind(str, enum.Enum):
    must = "must"
    avoid = "avoid"


class CampaignRule(Base):
    """One requirement of the brief: something a clip must do, or must not.
    Each is checked separately at verification time, and the result names the
    exact rule — so a rejection can say *which* requirement failed."""

    __tablename__ = "campaign_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[RuleKind] = mapped_column(Enum(RuleKind, name="rule_kind"), nullable=False)
    text: Mapped[str] = mapped_column(String(300), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    campaign: Mapped["Campaign"] = relationship(back_populates="rules")


class CampaignMembership(Base):
    """A creator's "Joined" state on a campaign — explicit, and separate
    from submitting. One row per (campaign, creator); leaving clears
    `left_at` rather than deleting the row, so a creator's history with a
    campaign (and their `Joined` badge before they ever submit) survives a
    leave/rejoin."""

    __tablename__ = "campaign_memberships"
    __table_args__ = (
        CheckConstraint(
            "left_at IS NULL OR left_at >= joined_at", name="ck_campaign_memberships_left_after_joined"
        ),
        Index(
            "ux_campaign_memberships_active",
            "campaign_id",
            "creator_id",
            unique=True,
            postgresql_where=text("left_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CampaignDraft(Base):
    """The campaign studio's autosave surface — everything `POST
    /campaigns` needs, accumulated screen by screen, before it's valid
    enough to become a real `Campaign`. `draft_answers` holds whatever
    subset of `CampaignCreate`'s fields have been saved so far, plus
    source-asset references (accepted here, not through a separate
    endpoint, until finalize — see production-api-inventory.md §H).
    `finalized_campaign_id` marks a spent draft: kept, not deleted, so a
    duplicate `finalize` call stays idempotent."""

    __tablename__ = "campaign_drafts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    current_step: Mapped[str | None] = mapped_column(String(40), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    draft_answers: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    finalized_campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    #: Stale, never-finalized drafts are cheap to expire; nothing sweeps
    #: this yet (no job wired), so it's a policy field, not enforced today.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
