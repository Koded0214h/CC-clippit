import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
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
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set by the creator/organisation onboarding endpoints; the frontend
    # routes a user to onboarding until this is set.
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Any token issued before this instant is dead — bumped on password
    # reset so a stolen session cannot outlive the change.
    tokens_valid_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # False for an account created by Google Sign-In that has never set a
    # local password — `password_hash` still holds a value (the column
    # stays NOT NULL), but it's an unguessable placeholder no login
    # attempt can ever match. Login-with-password checks this first.
    has_password: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    google_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Set instead of a hard delete, so campaigns/submissions/ledger rows
    # that reference this user's id keep their foreign keys intact.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- admin suspension (production-api-inventory.md §N) -----------------
    # Distinct from `deleted_at`: a suspension is reversible and scoped.
    # Empty `suspension_scopes` (the default) means nothing is suspended;
    # "access" blocks sign-in entirely (checked in deps.get_current_user),
    # "funding" blocks new campaign funding orders, "earning" blocks new
    # payout requests — each enforced at its own chokepoint, not centrally.
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspension_scopes: Mapped[list[str]] = mapped_column(ARRAY(String(20)), nullable=False, server_default="{}")
    suspension_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Informational only — nothing sweeps this yet to auto-restore the
    #: account, so a "temporary" suspension still needs a manual restore.
    suspension_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def onboarding_completed(self) -> bool:
        return self.onboarded_at is not None

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
    # What the creator recognises: "@tobioncam". Best effort at connect
    # time — a failed profile lookup never blocks the connection.
    handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    # Per-event toggles (see modules.auth.schemas.NotificationSettings).
    # Stored sparse: a missing key means "the default for that key".
    notifications: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
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


class Session(Base):
    """One signed-in device/browser. `GET /auth/sessions` lists these, not
    tokens — a session outlives any single access token and is what
    "sign out this device" actually revokes. `revoked_at` is checked on
    every request that carries a `sid` claim (see deps.get_current_user),
    so revoking a session invalidates its access tokens immediately
    rather than waiting for them to expire on their own."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    #: Best-effort, parsed from User-Agent at creation — never load-bearing.
    device_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RefreshToken(Base):
    """The bearer secret is never stored — only its hash — so a database
    leak can't be replayed. `id` is the public half returned to the
    client (`"<id>.<secret>"`); looking a token up by `id` first, then
    comparing the secret's hash, means a lookup never needs a table scan.

    Rotation: each refresh consumes one row (`used_at` set) and creates
    the next (`replaced_by_id` links them). A refresh call presenting an
    already-used token is treated as token theft — reuse — and revokes
    the whole session, not just that token, on the reasoning that a
    legitimate client never replays a token it already exchanged."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class AuthCodePurpose(str, enum.Enum):
    email_verify = "email_verify"
    password_reset = "password_reset"


class AuthCode(Base):
    """A six-digit one-time code, stored only as an HMAC — a database leak
    must not hand out live codes. One live code per (user, purpose): a new
    request replaces the old one."""

    __tablename__ = "auth_codes"
    __table_args__ = (UniqueConstraint("user_id", "purpose", name="uq_auth_code_user_purpose"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    purpose: Mapped[AuthCodePurpose] = mapped_column(Enum(AuthCodePurpose, name="auth_code_purpose"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
