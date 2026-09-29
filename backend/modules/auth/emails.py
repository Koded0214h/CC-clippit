"""Transactional email bodies, with plain text and branded HTML versions.
Kept in one place so copy changes don't touch route logic. Codes are never
logged by callers. Only the console sender prints them, and only in
development."""

from core import email_layout
from core.config import get_settings
from core.email import EmailMessage


_NEXT_STEPS = {
    "creator": [
        ("Confirm your email", "Enter the code above on the screen you already have open."),
        ("Complete your profile", "Tell us what you make and connect the account you post from."),
        ("Browse campaigns", "Open a brief, submit your work, and track verified results."),
    ],
    "organisation": [
        ("Confirm your email", "Enter the code above on the screen you already have open."),
        ("Complete your organisation profile", "Add the details creators need to recognise your brand."),
        ("Create a campaign", "Choose the outcomes, write the brief, and set the campaign budget."),
    ],
}


def verification_email(to: str, code: str, role: str | None = None) -> EmailMessage:
    minutes = get_settings().otp_ttl_minutes
    return EmailMessage(
        to=to,
        subject="Your Clippit verification code",
        text=(
            f"Clippit email confirmation code: {code}\n\n"
            f"It expires in {minutes} minutes. If you didn't create a Clippit account, ignore this email."
        ),
        html=email_layout.render(
            tag="Email confirmation",
            eyebrow="Clippit account",
            title="Confirm your email.",
            intro="Enter this code on the verification screen to confirm that this email belongs to you.",
            code=code,
            expires=f"Expires in {minutes} minutes",
            steps=_NEXT_STEPS.get(role or ""),
            note="Do not share this code. Clippit will never ask for it by phone, direct message, or email. "
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
            "If you weren't expecting this, ignore it. Nothing is created until the link is used."
        ),
        html=email_layout.render(
            tag="Operator invitation",
            eyebrow="Clippit admin",
            title="You have been invited.",
            intro=f"{invited_by} invited you to a Clippit operator account. Use the secure link below to set your password.",
            button=email_layout.Button("Accept invitation", link),
            note="If you were not expecting this invitation, ignore this email. Nothing is created until the link is used.",
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
            f"It expires in {minutes} minutes. If you didn't ask for this, you can ignore it. "
            "your password hasn't changed."
        ),
        html=email_layout.render(
            tag="Password reset",
            eyebrow="Account security",
            title="Reset your password.",
            intro="Enter this code on the password reset screen. After it is confirmed, you can choose a new password.",
            code=code,
            expires=f"Expires in {minutes} minutes",
            note="If you did not request a password reset, ignore this email. Your password has not changed.",
            preheader=f"{code} is your Clippit recovery code. It expires in {minutes} minutes.",
        ),
    )


def remember_device_email(to: str, code: str) -> EmailMessage:
    minutes = get_settings().otp_ttl_minutes
    return EmailMessage(
        to=to,
        subject="Confirm this device for Clippit",
        text=(
            f"Use {code} to keep this device signed in to Clippit.\n\n"
            f"It expires in {minutes} minutes. If this wasn't you, do not share the code."
        ),
        html=email_layout.render(
            tag="Device confirmation",
            eyebrow="Account security",
            title="Confirm this device.",
            intro="Enter this code in Clippit to keep this browser signed in until you sign out or remove the device.",
            code=code,
            expires=f"Expires in {minutes} minutes",
            note="If this wasn't you, do not share this code. You can remove signed-in devices from Security settings.",
            preheader=f"{code} confirms this device for Clippit.",
            reason="You're receiving this because Keep me signed in was selected during sign-in.",
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
            eyebrow="Clippit notification",
            title=title,
            intro=body,
            button=email_layout.Button("Open in Clippit", url) if url else None,
            preheader=body or title,
            reason="You're receiving this because email notifications are on in your Clippit settings.",
        ),
    )
