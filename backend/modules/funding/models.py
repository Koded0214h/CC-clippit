"""Campaign funding: the brand pays the pot in before the campaign opens.

One order per attempt. The amounts are frozen when the order is created —
changing a campaign's pot afterwards is not possible (the campaign is
locked in `pending_funding`), so what the brand was quoted is what is
confirmed. A confirmed order is the *only* thing that lets a campaign open.
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from core.money import MoneyColumn


class FundingStatus(str, enum.Enum):
    awaiting_payment = "awaiting_payment"
    #: The brand says they paid; the provider hasn't confirmed receipt yet.
    awaiting_confirmation = "awaiting_confirmation"
    confirmed = "confirmed"
    cancelled = "cancelled"
    failed = "failed"


class FundingMethod(str, enum.Enum):
    bank = "bank"
    card = "card"


class FundingOrder(Base):
    __tablename__ = "funding_orders"
    __table_args__ = (CheckConstraint("pot_amount > 0", name="ck_funding_pot_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    organisation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    #: What the brand sees and quotes: "CLP-2609-4F1A".
    reference: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    status: Mapped[FundingStatus] = mapped_column(
        Enum(FundingStatus, name="funding_status"),
        nullable=False,
        server_default=FundingStatus.awaiting_payment.value,
        index=True,
    )
    method: Mapped[FundingMethod] = mapped_column(Enum(FundingMethod, name="funding_method"), nullable=False)
    pot_amount: Mapped[Decimal] = mapped_column(MoneyColumn, nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(MoneyColumn, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(MoneyColumn, nullable=False)
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    # Where to send the money (bank method). Null for card.
    collection_bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    collection_account_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    collection_account_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    #: Hosted checkout page (Paystack): pays by bank transfer or card without
    #: card details ever touching this API.
    checkout_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
