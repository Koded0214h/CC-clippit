"""A file a user uploaded. The row is the ownership record: other modules
reference an upload by id and check `owner_id`, so one user can't attach
another user's file to their submission or profile."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # image | video | evidence
    #: `key`/`content_type`/`size_bytes` are null while a multipart upload
    #: is still in progress (`status == "pending"`) — nothing references a
    #: pending upload as owned media yet (`owned_upload` only accepts
    #: `ready`), so a half-finished upload can't be attached to anything.
    key: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    #: pending | ready | failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
