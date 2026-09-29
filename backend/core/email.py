"""Outbound email behind one small interface.

`ConsoleEmailSender` is the default: it logs the message and keeps the most
recent ones in memory, which is how a developer (or a test) reads the code
that would have arrived in an inbox. Nothing is ever sent to a real address
unless `EMAIL_BACKEND=smtp` or `EMAIL_BACKEND=resend` is configured.

Render blocks outbound SMTP (port 587/465), so use `resend` in production.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import time
from collections import deque
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from functools import lru_cache
from typing import Protocol

from . import delivery_stats
from .config import get_settings

logger = logging.getLogger("clippit.email")


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    #: Branded version; `text` is always sent too, as the plain-text part.
    html: str | None = None


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    def __init__(self, keep: int = 200) -> None:
        self.outbox: deque[EmailMessage] = deque(maxlen=keep)

    async def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)
        # Printed, not just logged: the stock logging config drops INFO, and
        # in development this line *is* the inbox (it carries the code).
        print(f"\n[email] to={message.to} subject={message.subject!r}\n{message.text}\n", flush=True)

    def last_to(self, address: str) -> EmailMessage | None:
        for message in reversed(self.outbox):
            if message.to.lower() == address.lower():
                return message
        return None


class SmtpEmailSender:
    def __init__(self, *, host: str, port: int, user: str, password: str, sender: str) -> None:
        self._host, self._port, self._user, self._password, self._sender = host, port, user, password, sender

    def _send_blocking(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["From"] = self._sender
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text)
        if message.html:
            mime.add_alternative(message.html, subtype="html")
        with smtplib.SMTP(self._host, self._port, timeout=15) as smtp:
            smtp.starttls()
            if self._user:
                smtp.login(self._user, self._password)
            smtp.send_message(mime)

    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(self._send_blocking, message)


class ResendEmailSender:
    """Sends via Resend's HTTP API — works on Render (no outbound SMTP needed)."""

    def __init__(self, *, api_key: str, sender: str) -> None:
        self._api_key = api_key
        self._sender = sender

    def _send_blocking(self, message: EmailMessage) -> None:
        import resend as _resend
        _resend.api_key = self._api_key
        payload = {
            "from": self._sender,
            "to": [message.to],
            "subject": message.subject,
            "text": message.text,
        }
        if message.html:
            payload["html"] = message.html
        _resend.Emails.send(payload)

    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(self._send_blocking, message)


class _Measured:
    """Times every send and records the outcome for the ops screens. Everything
    else (e.g. the console sender's `last_to`) passes straight through."""

    def __init__(self, inner: EmailSender) -> None:
        self._inner = inner

    async def send(self, message: EmailMessage) -> None:
        started = time.perf_counter()
        try:
            await self._inner.send(message)
        except Exception as exc:
            delivery_stats.record("email", False, (time.perf_counter() - started) * 1000, type(exc).__name__)
            raise
        delivery_stats.record("email", True, (time.perf_counter() - started) * 1000)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


@lru_cache
def get_email_sender() -> EmailSender:
    return _Measured(_build_email_sender())


def _build_email_sender() -> EmailSender:
    settings = get_settings()
    if settings.email_backend == "resend":
        if not settings.resend_api_key:
            raise RuntimeError("EMAIL_BACKEND=resend needs RESEND_API_KEY")
        return ResendEmailSender(api_key=settings.resend_api_key, sender=settings.email_from)
    if settings.email_backend == "smtp":
        if not settings.smtp_host:
            raise RuntimeError("EMAIL_BACKEND=smtp needs SMTP_HOST")
        return SmtpEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            user=settings.smtp_user,
            password=settings.smtp_password,
            sender=settings.email_from,
        )
    return ConsoleEmailSender()
