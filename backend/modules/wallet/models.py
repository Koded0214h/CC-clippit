"""The brand side of PRD V1's wallet money movement — a brand's wallet
"available balance" is a projection, not a stored number (same discipline
as creator earnings/payouts): it's `sum(succeeded refunds) − sum(live
withdrawals)`. See `service.available_balance`.

`OrganisationWithdrawal` mirrors `modules.payouts.models.Payout` closely
(bank details copied at send time, a separate `payout_status`-shaped
enum kept distinct so the two tables' migrations never entangle).
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


class WithdrawalStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"


class OrganisationWithdrawal(Base):
    __tablename__ = "organisation_withdrawals"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_org_withdrawal_amount_positive"),
        UniqueConstraint("organisation_id", "idempotency_key", name="uq_org_withdrawal_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[WithdrawalStatus] = mapped_column(
        Enum(WithdrawalStatus, name="org_withdrawal_status"), nullable=False, server_default=WithdrawalStatus.pending.value, index=True,
    )
    #: Gross — what the wallet is debited by. The provider is sent `amount - fee`.
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
