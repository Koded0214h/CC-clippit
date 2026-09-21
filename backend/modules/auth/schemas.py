import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

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
    email_verified: bool = False
    onboarding_completed: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class SocialAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    platform: Platform
    platform_user_id: str
    handle: str | None = None
    display_name: str | None = None
    connected_at: datetime
    #: When Intelligence last read one of this creator's posts on this
    #: platform. Null until they've submitted one.
    last_checked_at: datetime | None = None

    @classmethod
    def from_model(cls, account, last_checked_at: datetime | None = None) -> "SocialAccountOut":
        return cls(
            platform=account.platform,
            platform_user_id=account.platform_user_id,
            handle=account.handle,
            display_name=account.display_name,
            connected_at=account.created_at,
            last_checked_at=last_checked_at,
        )


class NotificationSettings(BaseModel):
    """Every toggle either workspace shows. One flat object so the frontend
    can bind switches without caring which role it is; keys a role never
    uses are simply ignored for that role."""

    # Creator settings → Notifications
    new_campaigns: bool = True
    submission_verdicts: bool = True
    earnings_payable: bool = True
    campaign_closing: bool = False
    # Brand settings → Campaign alerts
    funding_alerts: bool = True
    review_alerts: bool = True
    weekly_report: bool = False


class PreferencesOut(BaseModel):
    email_notifications: bool
    marketing_emails: bool
    theme: Theme
    notifications: NotificationSettings

    @classmethod
    def from_model(cls, prefs) -> "PreferencesOut":
        return cls(
            email_notifications=prefs.email_notifications,
            marketing_emails=prefs.marketing_emails,
            theme=prefs.theme,
            notifications=NotificationSettings(**(prefs.notifications or {})),
        )


class PreferencesUpdate(BaseModel):
    email_notifications: bool | None = None
    marketing_emails: bool | None = None
    theme: Theme | None = None
    notifications: NotificationSettings | None = None


class VerifyEmailRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
    #: Needed only when the request carries no session (the user opened the
    #: verify page on another device); ignored when signed in.
    email: EmailStr | None = None


class ResendCodeRequest(BaseModel):
    email: EmailStr | None = None


class CodeSentResponse(BaseModel):
    sent: bool = True
    #: Seconds before another code can be requested.
    resend_in: int


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class RecoveryCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


class ResetTokenResponse(BaseModel):
    reset_token: str


class ResetPasswordRequest(BaseModel):
    reset_token: str
    password: str

    @field_validator("password")
    @classmethod
    def password_is_strong(cls, value: str) -> str:
        if len(value) < 8 or not any(c.isdigit() for c in value):
            raise ValueError("Password must be at least 8 characters and include a number.")
        return value


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
