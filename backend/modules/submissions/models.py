"""Submissions — a creator's claim that a piece of content fulfills a
campaign. Owned by Koded's core-backend domain.

Deliberately thin: the submission's *own* lifecycle lives here (was it
made, was it withdrawn, did Intelligence even accept the URL), but
performance and trust are never duplicated onto this table — they're
read fresh from Intelligence's `/internal/submissions/{id}/performance`
every time, per the contract in architecture/intelligence-contracts.md.
No uniqueness constraint on (campaign_id, url): two creators submitting
the same post is a trust signal Intelligence's own design explicitly
wants visible, not a constraint violation.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class SubmissionStatus(str, enum.Enum):
    #: Intelligence accepted the URL and tracking has started (or is being
    #: retried on its own schedule — that detail lives on its side, not here).
    submitted = "submitted"
    #: Intelligence rejected the URL at registration time (bad link, content
    #: unavailable, creator's token expired, ...). See rejection_code.
    rejected = "rejected"
    #: Pulled by the creator or an admin. Terminal, like `rejected`.
    withdrawn = "withdrawn"


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    creator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # A core.platforms.Platform value — plain string, not a native enum, for
    # the same reason campaigns.platforms is: see decision D5.
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, name="submission_status"),
        nullable=False,
        server_default=SubmissionStatus.submitted.value,
    )
    rejection_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rejection_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
