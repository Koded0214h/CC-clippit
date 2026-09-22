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


def admin_invitation_email(to: str, link: str, invited_by: str) -> EmailMessage:
    return EmailMessage(
        to=to,
        subject="You've been invited to Clippit's admin",
        text=(
            f"{invited_by} invited you to a Clippit operator account.\n\n"
            f"Accept the invitation: {link}\n\n"
            "If you weren't expecting this, ignore it — nothing is created until the link is used."
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
