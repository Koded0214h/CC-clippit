"""Outbound email behind one small interface.

`ConsoleEmailSender` is the default: it logs the message and keeps the most
recent ones in memory, which is how a developer (or a test) reads the code
that would have arrived in an inbox. Nothing is ever sent to a real address
unless `EMAIL_BACKEND=smtp` is configured.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from collections import deque
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from functools import lru_cache
from typing import Protocol

from .config import get_settings

logger = logging.getLogger("clippit.email")


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str


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
        with smtplib.SMTP(self._host, self._port, timeout=15) as smtp:
            smtp.starttls()
            if self._user:
                smtp.login(self._user, self._password)
            smtp.send_message(mime)

    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(self._send_blocking, message)


@lru_cache
def get_email_sender() -> EmailSender:
    settings = get_settings()
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
