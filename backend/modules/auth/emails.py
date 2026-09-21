"""Plain-text transactional email bodies. Kept in one place so copy changes
don't touch route logic. Codes are never logged by callers — only the
console sender prints them, and only in development."""

from core.config import get_settings
from core.email import EmailMessage


def verification_email(to: str, code: str) -> EmailMessage:
    minutes = get_settings().otp_ttl_minutes
    return EmailMessage(
        to=to,
        subject="Your Clippit verification code",
        text=(
            f"Your Clippit verification code is {code}.\n\n"
            f"It expires in {minutes} minutes. If you didn't create a Clippit account, ignore this email."
        ),
    )


def recovery_email(to: str, code: str) -> EmailMessage:
    minutes = get_settings().otp_ttl_minutes
    return EmailMessage(
        to=to,
        subject="Your Clippit recovery code",
        text=(
            f"Use {code} to reset your Clippit password.\n\n"
            f"It expires in {minutes} minutes. If you didn't ask for this, you can ignore it — "
            "your password hasn't changed."
        ),
    )
