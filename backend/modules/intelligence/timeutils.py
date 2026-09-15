"""Two time helpers, shared so the same rule applies everywhere."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Always timezone-aware. A naive `datetime.now()` anywhere in this
    module would eventually be compared against an aware one and raise."""
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """SQLite hands back naive datetimes even for `DateTime(timezone=True)`,
    while adapters and `utcnow()` always produce aware ones — and comparing
    the two raises. Postgres doesn't have this problem; normalizing on read
    keeps the same code correct on both."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
