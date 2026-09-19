import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Role(str, enum.Enum):
    creator = "creator"
    organisation = "organisation"  # the "event manager" actor in the architecture doc
    admin = "admin"


class Platform(str, enum.Enum):
    """Same six values as `core.platforms.Platform`. Kept as a local enum
    so the existing Postgres type named `platform` stays the column type
    (decision D5). Values must stay spelled identically."""

    tiktok = "tiktok"
    facebook = "facebook"
    instagram = "instagram"
    threads = "threads"
    x = "x"
    youtube = "youtube"


class Theme(str, enum.Enum):
    system = "system"
    light = "light"
    dark = "dark"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    social_accounts: Mapped[list["SocialAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    preferences: Mapped["UserPreferences"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )


class SocialAccount(Base):
    __tablename__ = "social_accounts"
    __table_args__ = (UniqueConstraint("user_id", "platform", name="uq_user_platform"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[Platform] = mapped_column(Enum(Platform, name="platform"), nullable=False)
    platform_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token: Mapped[str] = mapped_column(String(2048), nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="social_accounts")


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    email_notifications: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    marketing_emails: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    theme: Mapped[Theme] = mapped_column(Enum(Theme, name="theme"), nullable=False, server_default="system")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="preferences")


class RevokedToken(Base):
    """One row per revoked access token (its `jti`), checked on every
    authenticated request. Only holds already-expired-or-logged-out tokens
    long enough for their own `exp` to pass — safe to prune rows where
    expires_at < now() on a schedule once this needs to scale."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
