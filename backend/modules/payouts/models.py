"""Money leaving Clippit for a creator's bank account.

A payout is created only from *payable* earnings (past the holding period),
and each payout records exactly which entries it consumed
(`payout_allocations`) — that is the receipt's "where this money came from",
and what lets a failed transfer release its money back.

The bank details are copied onto the payout (`bank_*`): a creator changing
their account later must not rewrite where a past payout went.
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from core.money import MoneyColumn


class PayoutStatus(str, enum.Enum):
    #: Money is reserved; the provider hasn't been asked (or hasn't answered).
    pending = "pending"
    processing = "processing"
    succeeded = "succeeded"
    #: The provider refused or the transfer bounced. Allocations are released.
    failed = "failed"


class Payout(Base):
    __tablename__ = "payouts"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payout_amount_positive"),
        UniqueConstraint("creator_id", "idempotency_key", name="uq_payout_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    #: "CLP-260920-1847" — what the creator quotes to support.
    reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    #: Supplied by the client so a double-tapped "Confirm withdrawal" is one payout.
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[PayoutStatus] = mapped_column(
        Enum(PayoutStatus, name="payout_status"),
        nullable=False,
        server_default=PayoutStatus.pending.value,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(MoneyColumn, nullable=False)
    fee: Mapped[Decimal] = mapped_column(MoneyColumn, nullable=False, server_default="0")
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    bank_code: Mapped[str] = mapped_column(String(10), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    account_name: Mapped[str] = mapped_column(String(160), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    initiated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PayoutAllocation(Base):
    """`amount` of one earning entry that a payout consumed."""

    __tablename__ = "payout_allocations"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_allocation_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payout_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payouts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("earning_entries.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MoneyColumn, nullable=False)
