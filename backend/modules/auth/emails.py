"""Transactional email bodies — plain text plus the branded HTML version.
Kept in one place so copy changes don't touch route logic. Codes are never
logged by callers — only the console sender prints them, and only in
development."""

from core import email_layout
from core.config import get_settings
from core.email import EmailMessage


_NEXT_STEPS = {
    "creator": [
        ("Confirm your email", "Enter the code above. You're doing it now."),
        ("Connect your account", "Link the TikTok, Instagram, Facebook, X or YouTube account you post on."),
        ("Join a campaign and post", "Submit your clip link and earn on verified views."),
    ],
    "organisation": [
        ("Confirm your email", "Enter the code above. You're doing it now."),
        ("Set up your brand profile", "Add your brand name and logo so creators know who you are."),
        ("Launch a campaign", "Set the brief and rate, fund it, and pay only for verified views."),
    ],
}


def verification_email(to: str, code: str, role: str | None = None) -> EmailMessage:
    minutes = get_settings().otp_ttl_minutes
    return EmailMessage(
        to=to,
        subject="Your Clippit verification code",
        text=(
            f"Your Clippit verification code is {code}.\n\n"
            f"It expires in {minutes} minutes. If you didn't create a Clippit account, ignore this email."
        ),
        html=email_layout.render(
            tag="Verify email",
            eyebrow="One step left",
            title="Here's your code.",
            intro="Enter this on the verification screen to confirm your email and finish setting up your Clippit account.",
            code=code,
            expires=f"Expires in {minutes} minutes",
            steps=_NEXT_STEPS.get(role or ""),
            note="Keep it to yourself — Clippit will never ask for this code by phone, DM or email. "
            "If you didn't create an account, you can ignore this email.",
            preheader=f"{code} is your Clippit verification code. It expires in {minutes} minutes.",
            reason="You're receiving this because this address was used to sign up at clippit.click.",
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
        html=email_layout.render(
            tag="Admin invite",
            eyebrow="You're invited",
            title="Join the Clippit operator team.",
            intro=f"{invited_by} invited you to a Clippit operator account. Accept below to set your password and get started.",
            button=email_layout.Button("Accept invitation", link),
            note="Weren't expecting this? — Ignore it. Nothing is created until the link is used.",
            preheader=f"{invited_by} invited you to a Clippit operator account.",
            reason="You're receiving this because a Clippit admin invited this address.",
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
        html=email_layout.render(
            tag="Password reset",
            eyebrow="Reset your password",
            title="Let's get you back in.",
            intro="Enter this code on the reset screen, then choose a new password.",
            code=code,
            expires=f"Expires in {minutes} minutes",
            note="Didn't ask for this? — You can ignore it. Your password hasn't changed.",
            preheader=f"{code} is your Clippit recovery code. It expires in {minutes} minutes.",
        ),
    )


def notification_email(to: str, title: str, body: str = "", link: str | None = None) -> EmailMessage:
    """In-app notifications mirrored to email (notifications.service.notify)."""
    url = email_layout.absolute_link(link) if link else None
    return EmailMessage(
        to=to,
        subject=title,
        text="\n\n".join(part for part in (body or title, url) if part),
        html=email_layout.render(
            tag="Update",
            eyebrow="From your Clippit account",
            title=title,
            intro=body,
            button=email_layout.Button("Open in Clippit", url) if url else None,
            preheader=body or title,
            reason="You're receiving this because email notifications are on in your Clippit settings.",
        ),
    )
