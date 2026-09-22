import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class LegalAcceptance(Base):
    """One consent record: this user accepted this document's version, for
    this reason, at this time. Idempotent per (user, slug, version) — a
    re-submission of the same version is a no-op, not a duplicate row."""

    __tablename__ = "legal_acceptances"
    __table_args__ = (UniqueConstraint("user_id", "slug", "version", name="uq_legal_acceptance_user_doc_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    #: What required consent — "signup", "campaign_funding", etc.
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    #: Hashed, never raw: enough to investigate a dispute, not enough to
    #: itself be personal tracking data at rest.
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
