"""Storage for platform observations.

Two tables, and the split between them is the whole design:

- **`social_content`** — mutable-ish identity. One row per submission: which
  post on which platform, who posted it, when. Re-ingesting a submission
  finds this row again rather than creating another.
- **`metric_snapshots`** — immutable observations. One row *per reading*,
  forever. Nothing in the codebase may `UPDATE` one. A view count without
  its history can't produce a growth rate and can't be audited, which is
  why §10 and §18 of the implementation plan insist on the time series.

Derived features (velocity, ratios) deliberately live in neither: they get
their own table in Stage 4 so they can be recomputed when the formulas
improve, without touching a single observation.

### Two portability choices worth knowing

**Enums are stored as VARCHAR + CHECK, not native Postgres enum types**
(`native_enum=False`). Koded's auth module already owns a Postgres type
literally named `platform` holding four values; ours needs six. Creating a
second native type with a clashing concept invites a migration conflict,
and native enums can't drop values. A checked VARCHAR sidesteps decision D5
entirely and is far easier to widen when YouTube lands.

**Generic `sa.Uuid` and `JSON`-with-JSONB-variant, not the Postgres-only
types.** Production is Postgres and gets real `UUID`/`JSONB`; the test
suite can then run the same models on in-memory SQLite, so Stage 2's exit
condition is reproducible with no database server. The tradeoff is honest:
these tests prove the *logic*, not Postgres-specific behaviour.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from core.platforms import Platform
from integrations.social.base import ContentKind, PostType

from .scheduling import TrackingStatus

#: JSONB in production, plain JSON on SQLite under test.
RawJSON = sa.JSON().with_variant(JSONB, "postgresql")


def _checked_enum(python_enum: type, name: str) -> sa.Enum:
    # create_constraint defaults to False in SQLAlchemy 1.4+, which would
    # leave these as bare VARCHARs — the CHECK is the entire point of
    # giving up the native type, so ask for it explicitly.
    return sa.Enum(python_enum, name=name, native_enum=False, create_constraint=True, length=32)


class SocialContent(Base):
    """A submitted post, resolved to something a platform API can address."""

    __tablename__ = "social_content"
    __table_args__ = (
        # One content row per submission — this is what makes re-ingesting
        # idempotent instead of duplicating.
        sa.UniqueConstraint("submission_id", name="uq_social_content_submission"),
        # Deliberately NOT unique: two creators submitting the same video is
        # exactly the kind of thing the trust engine needs to be able to
        # see, so the schema must let it happen and be queryable.
        sa.Index("ix_social_content_platform_content", "platform", "platform_content_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)

    # Core's identifiers. No foreign keys: `submissions`, `campaigns` and
    # `users` are Koded's tables, and pointing at them would couple our
    # migrations to his. We store the IDs and resolve through his API.
    submission_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)
    campaign_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)
    creator_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)

    platform: Mapped[Platform] = mapped_column(
        _checked_enum(Platform, "social_content_platform"), nullable=False
    )
    platform_content_id: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    url: Mapped[str] = mapped_column(sa.String(1024), nullable=False)
    author_username: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    kind: Mapped[ContentKind] = mapped_column(
        _checked_enum(ContentKind, "social_content_kind"), nullable=False
    )
    post_type: Mapped[PostType] = mapped_column(
        _checked_enum(PostType, "social_content_post_type"), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    raw_content: Mapped[dict[str, Any]] = mapped_column(RawJSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )

    snapshots: Mapped[list["MetricSnapshot"]] = relationship(
        back_populates="content", cascade="all, delete-orphan"
    )
    tracking: Mapped["ContentTracking | None"] = relationship(
        back_populates="content", cascade="all, delete-orphan", uselist=False
    )


class MetricSnapshot(Base):
    """One observation of one post's counters. Append-only, forever.

    `captured_at` is when the *platform* reported these numbers;
    `created_at` is when we wrote the row. They're usually milliseconds
    apart and occasionally hours, when a job was backed up — and only the
    first one is valid for computing velocity.
    """

    __tablename__ = "metric_snapshots"
    __table_args__ = (
        # A safety net against an exactly-duplicated write, and a statement
        # of intent: one observation per instant per piece of content.
        sa.UniqueConstraint("content_id", "captured_at", name="uq_metric_snapshot_instant"),
        # The pipeline's hottest read is "latest snapshot for this content",
        # closely followed by "this content's series in order".
        sa.Index("ix_metric_snapshots_content_captured", "content_id", "captured_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    content_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("social_content.id", ondelete="CASCADE"), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    # All nullable, all for the same reason: a platform that doesn't report
    # a metric must not be recorded as reporting zero.
    views: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    likes: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    comments: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    shares: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    saves: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    reach: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    impressions: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)

    #: Which API produced this, e.g. "tiktok.display_api". Provenance is
    #: mandatory: no observation without its origin.
    source: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    raw_metrics: Mapped[dict[str, Any]] = mapped_column(RawJSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    content: Mapped["SocialContent"] = relationship(back_populates="snapshots")


class ContentFeature(Base):
    """What one observation *means*, relative to the one before it.

    Snapshots say "12,400 views at 09:00". Features say "2,100 more than
    last time, 87 an hour, 7.5% engagement". Keeping them in separate
    tables is the rule from §10 of the plan, and the reason is practical
    rather than tidy: these numbers are guesses that will be revised.
    When we improve how velocity is calculated, or find a bug in it, we
    delete every row here and rebuild from the snapshots. That's only
    possible because the snapshots were never touched.

    One row per snapshot, enforced by a unique constraint. That makes
    recomputation idempotent (compute the same snapshot twice, get one
    row) and gives the trust engine what it actually needs in Stage 5: not
    just today's velocity, but the *series* of velocities, which is where
    a spike becomes visible.
    """

    __tablename__ = "content_features"
    __table_args__ = (
        sa.UniqueConstraint("snapshot_id", name="uq_content_feature_snapshot"),
        sa.Index("ix_content_features_content_computed", "content_id", "computed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    content_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("social_content.id", ondelete="CASCADE"), nullable=False
    )
    #: The observation these values were derived from. Features are a pure
    #: function of this snapshot and its predecessor, which is what makes
    #: the whole table disposable.
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("metric_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    computed_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    #: Null on the first observation of a post — one point can't produce a
    #: rate of change, and zero would be a lie.
    incremental_views: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    view_velocity_per_hour: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    growth_rate: Mapped[float | None] = mapped_column(sa.Float, nullable=True)

    #: Engagement ratios, from cumulative totals rather than deltas —
    #: "1.2% of viewers liked it" is a property of the post, not of the
    #: gap between two polls.
    like_view_ratio: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    comment_view_ratio: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    share_view_ratio: Mapped[float | None] = mapped_column(sa.Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class ContentTracking(Base):
    """The poller's state for one piece of content — and the only mutable
    table this module owns.

    Kept separate from `social_content` on purpose. That table is what a
    post *is*, and reads cleanly as a record; this one is operational
    churn (next due time, failure counters, lease stamps) rewritten on
    every tick. Mixing them would mean every poll dirties the identity row
    and the two would be impossible to reason about separately.

    `next_poll_at` doubles as the work queue: "what's due" is
    `status = 'active' AND next_poll_at <= now()`, which is one index scan
    rather than a separate queue system to operate.
    """

    __tablename__ = "content_tracking"
    __table_args__ = (
        # The due-work query, and the only index this table needs.
        sa.Index("ix_content_tracking_due", "status", "next_poll_at"),
    )

    content_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("social_content.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[TrackingStatus] = mapped_column(
        _checked_enum(TrackingStatus, "content_tracking_status"),
        nullable=False,
        default=TrackingStatus.active,
    )
    next_poll_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    last_polled_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    #: Reset to zero by any success. Drives the backoff curve and the
    #: dead-letter threshold, so it counts *consecutive* failures only.
    consecutive_failures: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    #: Stable code from `scheduling.decide()` — also carries the reason a
    #: row was stopped, which is what the product surfaces to a creator.
    last_error_code: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )

    content: Mapped["SocialContent"] = relationship(back_populates="tracking")
