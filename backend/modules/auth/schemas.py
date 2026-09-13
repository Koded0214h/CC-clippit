import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from .models import Platform, Role, Theme


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: Role

    @field_validator("password")
    @classmethod
    def password_is_strong(cls, value: str) -> str:
        if len(value) < 8 or not any(c.isdigit() for c in value):
            raise ValueError("Password must be at least 8 characters and include a number.")
        return value

    @field_validator("role")
    @classmethod
    def cannot_self_signup_as_admin(cls, value: Role) -> Role:
        if value == Role.admin:
            raise ValueError("Admin accounts cannot be created through signup.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: Role
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class SocialAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    platform: Platform
    platform_user_id: str
    connected_at: datetime

    @classmethod
    def from_model(cls, account) -> "SocialAccountOut":
        return cls(
            platform=account.platform,
            platform_user_id=account.platform_user_id,
            connected_at=account.created_at,
        )


class PreferencesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email_notifications: bool
    marketing_emails: bool
    theme: Theme


class PreferencesUpdate(BaseModel):
    email_notifications: bool | None = None
    marketing_emails: bool | None = None
    theme: Theme | None = None


class ProfileOut(BaseModel):
    """What the profile page loads in one call: who the user is, what
    they've connected, and their preferences — this is also where the
    frontend renders the "Connect TikTok / Facebook / ..." buttons from,
    since social connections are a profile action, not a signup mechanism."""

    user: UserOut
    social_accounts: list[SocialAccountOut]
    preferences: PreferencesOut


class InternalUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: Role


class InternalTokenOut(BaseModel):
    access_token: str
    platform_user_id: str
    expires_at: datetime | None
