"""Safety/abuse reports against something else on the platform — a
campaign, a public profile, or a clip — as opposed to `modules.disputes`,
which is about a customer's *own* money or verdict record.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class ReportTargetType(str, enum.Enum):
    campaign = "campaign"
    creator_profile = "creator_profile"
    organisation_profile = "organisation_profile"
    submission = "submission"


class ReportStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"


class ReportResolution(str, enum.Enum):
    no_action = "no_action"
    content_restricted = "content_restricted"
    campaign_paused = "campaign_paused"
    account_sanctioned = "account_sanctioned"
    escalated = "escalated"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: Never returned to anyone but the reporter themselves and an admin —
    #: see the docstring above and router.py's `/me` scoping.
    reporter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_type: Mapped[ReportTargetType] = mapped_column(Enum(ReportTargetType, name="report_target_type"), nullable=False, index=True)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(60), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_upload_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, server_default="{}")
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status"), nullable=False, server_default=ReportStatus.open.value, index=True
    )
    resolution: Mapped[ReportResolution | None] = mapped_column(Enum(ReportResolution, name="report_resolution"), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
