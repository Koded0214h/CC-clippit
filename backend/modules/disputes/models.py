"""Escalated, structured cases against a specific money/verdict record —
distinct from a support ticket (a question) and from a submission appeal
(the fast, first-line review already built into `modules.submissions`).

`resource_type`/`resource_id` are a loose reference, same as
`audit_events` and support tickets — see `service.RESOURCE_TYPES` for
what each type resolves to (owner, reference time, amount at risk).
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ARRAY, Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from core.money import MoneyColumn


class DisputeType(str, enum.Enum):
    submission_verdict = "submission_verdict"
    earning_entry = "earning_entry"
    payout = "payout"
    funding_order = "funding_order"
    refund = "refund"


class DisputeStatus(str, enum.Enum):
    open = "open"
    awaiting_customer = "awaiting_customer"
    resolved = "resolved"
    withdrawn = "withdrawn"


class DisputeResolution(str, enum.Enum):
    upheld = "upheld"  # the customer was right
    denied = "denied"
    partial = "partial"


class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[DisputeType] = mapped_column(Enum(DisputeType, name="dispute_type"), nullable=False, index=True)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DisputeStatus] = mapped_column(
        Enum(DisputeStatus, name="dispute_status"), nullable=False, server_default=DisputeStatus.open.value, index=True
    )
    amount_at_risk: Mapped[Decimal | None] = mapped_column(MoneyColumn, nullable=True)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolution: Mapped[DisputeResolution | None] = mapped_column(Enum(DisputeResolution, name="dispute_resolution"), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    customer_last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list["DisputeMessage"]] = relationship(
        back_populates="dispute", cascade="all, delete-orphan", order_by="DisputeMessage.created_at"
    )


class DisputeMessage(Base):
    __tablename__ = "dispute_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dispute_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("disputes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    from_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_upload_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    dispute: Mapped["Dispute"] = relationship(back_populates="messages")
