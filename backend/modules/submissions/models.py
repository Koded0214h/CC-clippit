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

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


class VerificationStatus(str, enum.Enum):
    """Where a submission is against the brief — separate from
    `SubmissionStatus`, which is whether the *link* was accepted.

    Nothing earns until this is `approved`."""

    checking = "checking"
    #: Waiting on a human (the brand, or an admin for an appeal).
    needs_review = "needs_review"
    approved = "approved"
    #: A requirement failed. The creator can appeal or submit a correction.
    rejected = "rejected"
    appealed = "appealed"


class RequirementVerdict(str, enum.Enum):
    passed = "pass"
    failed = "fail"
    review = "review"


class AppealStatus(str, enum.Enum):
    open = "open"
    upheld = "upheld"  # the original rejection stands
    overturned = "overturned"  # the creator was right


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
    #: A label for lists ("Hunger interrupted the group chat"). Creator-supplied.
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: The original file the creator uploaded, for the reviewer to watch.
    video_upload_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="SET NULL"), nullable=True
    )
    #: Set only on a correction created via `POST .../resubmit`. The
    #: predecessor's own verdict, requirement results, and appeal are
    #: never rewritten — this just links the chain.
    resubmitted_from_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="SET NULL"), nullable=True
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status"),
        nullable=False,
        server_default=VerificationStatus.checking.value,
        index=True,
    )
    #: 0-100, when a verifier produces one. Null for a plain human review.
    verification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    #: The one-line reason shown in review queues.
    verification_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    verdict_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Who decided. Null means an automated verifier.
    verdict_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SubmissionRequirementResult(Base):
    """One brief requirement's verdict for one submission. The requirement
    text is copied here on purpose: the brand may reword a rule later, and a
    verdict must keep saying what it actually checked."""

    __tablename__ = "submission_requirement_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign_rules.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(8), nullable=False)  # must | avoid
    text: Mapped[str] = mapped_column(String(300), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    verdict: Mapped[RequirementVerdict] = mapped_column(
        Enum(RequirementVerdict, name="requirement_verdict"), nullable=False
    )
    #: "Found at 00:08 and 00:19", "Tag not found in the public caption".
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubmissionAppeal(Base):
    """A creator's challenge to a rejection. The original verdict is never
    edited — the appeal is a second record beside it (audit trail)."""

    __tablename__ = "submission_appeals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_upload_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[AppealStatus] = mapped_column(
        Enum(AppealStatus, name="appeal_status"), nullable=False, server_default=AppealStatus.open.value
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
