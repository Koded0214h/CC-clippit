"""Create notifications. Other modules call `notify()` and never write a
row themselves, so the user's toggles are honoured in exactly one place.

`kind` maps to a toggle in `NotificationSettings`. A kind with no toggle
(a payout failing, say) always delivers: those are about the user's money
and must not be silenceable by a marketing-style switch.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.email import get_email_sender
from modules.auth.emails import notification_email
from modules.auth.models import User, UserPreferences
from modules.auth.schemas import NotificationSettings

from .models import Notification

logger = logging.getLogger("clippit.notifications")

#: kind -> the NotificationSettings key that gates it (None = always on).
KIND_TOGGLES: dict[str, str | None] = {
    "new_campaign": "new_campaigns",
    "submission_verdict": "submission_verdicts",
    "earnings_payable": "earnings_payable",
    "campaign_closing": "campaign_closing",
    "funding": "funding_alerts",
    "review_needed": "review_alerts",
    "weekly_report": "weekly_report",
    # Money outcomes and account safety: never silenced.
    "payout": None,
    "appeal_decision": None,
}


async def notify(
    db: AsyncSession,
    user_id: uuid.UUID,
    kind: str,
    title: str,
    body: str = "",
    link: str | None = None,
) -> Notification | None:
    """Adds the row to the caller's session (the caller commits, so a
    notification is only ever saved together with the thing it announces)."""
    prefs = await db.get(UserPreferences, user_id)
    toggle = KIND_TOGGLES.get(kind)
    if toggle is not None:
        settings = NotificationSettings(**((prefs.notifications if prefs else None) or {}))
        if not getattr(settings, toggle):
            return None

    note = Notification(user_id=user_id, kind=kind, title=title, body=body, link=link)
    db.add(note)

    if prefs is None or prefs.email_notifications:
        user = await db.get(User, user_id)
        if user is not None:
            try:
                await get_email_sender().send(notification_email(user.email, title, body, link))
            except Exception:  # noqa: BLE001 — the in-app row still stands
                logger.exception("notification email to %s failed", user.email)
    return note
