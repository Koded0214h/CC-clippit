"""An append-only record of the actions that matter: money moving, verdicts
given, campaigns opening and closing. It is a log for humans and auditors,
never a source of truth — balances are derived from the domain tables
(earning entries, payouts, funding orders), not summed from here.

Rows are only ever inserted. There is deliberately no update or delete path.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from core.money import MoneyColumn


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: Who did it. Null for the system (a scheduled job, a provider webhook).
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    submission_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(MoneyColumn, nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
