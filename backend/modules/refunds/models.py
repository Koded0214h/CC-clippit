"""Refunding the unused share of a campaign's pot.

**Open policy question, not resolved here**: whether the 1.5% funding fee
is itself refundable. This implementation refunds only the *unspent pot*
(`pot_amount - spent`) and never the fee — the fee is treated as earned by
Clippit at funding time, the same way a payment processor's own fee isn't
returned on a refund. That's an assumption, not a legal/tax decision;
confirm it before launch.
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from core.money import MoneyColumn


class RefundStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"


class Refund(Base):
    __tablename__ = "refunds"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_refund_amount_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    organisation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    funding_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("funding_orders.id"), nullable=False)
    #: Ours — what we ask the provider to refund, distinct from the
    #: original funding order's reference (which the provider's refund
    #: actually targets — see `create_refund`'s `collection_reference`).
    reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    amount: Mapped[Decimal] = mapped_column(MoneyColumn, nullable=False)
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus, name="refund_status"), nullable=False, server_default=RefundStatus.pending.value
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
