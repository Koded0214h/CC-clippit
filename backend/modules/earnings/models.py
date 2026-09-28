"""What creators have earned. Append-only entries, plus one running account
per submission so settlement is idempotent.

Money never floats: every amount is `Numeric(14, 2)`/`Decimal`.

    earning_accounts  one row per submission. Holds the cumulative view count
                      last settled against and how many whole thousands have
                      already been billed — which is what makes settling twice
                      a no-op and stops partial thousands from being lost
                      (see services.settle_submission).
    earning_entries   one row per accrual. Immutable. `payable_at` is the end
                      of the holding period; an entry is spendable from then.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from core.money import MoneyColumn


class EarningAccount(Base):
    __tablename__ = "earning_accounts"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), primary_key=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    creator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    #: Latest cumulative verified views seen (never decreases: platforms
    #: revise counts down, money is not clawed back by a reading).
    cumulative_views: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    billed_thousands: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    accrued_amount: Mapped[Decimal] = mapped_column(MoneyColumn, nullable=False, server_default="0")
    #: The Intelligence snapshot last settled against (decision D18).
    last_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    #: Why accrual is paused, if it is: `trust_flagged`, `pot_exhausted`, ...
    blocked_reason: Mapped[str | None] = mapped_column(String(48), nullable=True)
    last_settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- admin trust override and release hold (production-api-inventory.md §N) --
    # `admin_trust_override`: null defers to Intelligence's own read on
    # every tick; True forces accrual to proceed even if Intelligence
    # still reports flagged (POST .../trust/clear); False forces it
    # blocked even if Intelligence reports clean (POST .../trust/confirm).
    # See earnings.service.settle_submission for where this is applied.
    admin_trust_override: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    #: Set by POST /admin/earnings/{submission_id}/hold: blocks this
    #: submission's entries from payout reservation (earnings.queries and
    #: payouts.service.reserve both check it) without touching accrual —
    #: separate from a trust block, which stops new money from accruing
    #: at all. Money already payable just... isn't, until released.
    release_hold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hold_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class MetricEarningAccount(Base):
    """Idempotent payout cursor for one submitted clip and outcome."""

    __tablename__ = "metric_earning_accounts"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "creator_id",
            "submission_id",
            "metric_type",
            name="uq_metric_earning_account",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    creator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_type: Mapped[str] = mapped_column(String(24), nullable=False)
    observed_total: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    billed_batches: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    accrued_amount: Mapped[Decimal] = mapped_column(MoneyColumn, nullable=False, server_default="0")
    last_settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EarningEntry(Base):
    __tablename__ = "earning_entries"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_earning_amount_positive"),
        CheckConstraint("thousands > 0", name="ck_earning_thousands_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submissions.id"), nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    creator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MoneyColumn, nullable=False)
    metric_type: Mapped[str] = mapped_column(String(24), nullable=False, server_default="view")
    billable_units: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    unit_size: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1000")
    #: Views gained since the previous entry — what the history table shows.
    billable_views: Mapped[int] = mapped_column(BigInteger, nullable=False)
    #: Cumulative views at the reading this entry settled against.
    views_total: Mapped[int] = mapped_column(BigInteger, nullable=False)
    #: Whole thousands this entry billed.
    thousands: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    #: `<submission_id>:<thousands billed after this entry>` — unique, so a
    #: retried or concurrent settlement cannot pay the same thousand twice.
    reference: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    accrued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    payable_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    #: Set once the creator has been told this became withdrawable, so the
    #: "Earnings become payable" notice is sent once per entry, never twice.
    payable_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
