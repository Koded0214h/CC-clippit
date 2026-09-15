"""When to poll a post again, and what to do when a poll fails.

Every function here is pure — age in, interval out; exception in, decision
out. No database, no clock, no network. That's deliberate: this is the
file that encodes judgement calls we'll argue about for months (how often
is often enough? when do we give up?), and being able to re-read those
rules as a table of plain functions beats spelunking a worker loop.

The two halves:

- **Cadence.** A post's interesting life is front-loaded. Most of a
  TikTok's views land in the first day, so that's where the resolution
  has to be; a month-old post barely moves and polling it hourly just
  burns rate limit. Intervals widen with age.
- **Failure handling.** Decision D13 put retry logic here rather than in
  adapters, so this is where an exception class becomes an action: wait
  and retry, stop polling, or give up and dead-letter for a human.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import timedelta

from integrations.social.base import (
    AdapterError,
    CapabilityNotSupported,
    ContentNotFound,
    ContentUnavailable,
    CreatorTokenExpired,
    RateLimited,
    UpstreamError,
)

from .errors import MissingCreatorToken, TokenLookupFailed, UrlNotRecognized


class TrackingStatus(str, enum.Enum):
    """Lives here rather than next to the table so the policy layer stays
    free of SQLAlchemy; `models.py` imports it."""

    #: Being polled on the cadence below.
    active = "active"
    #: Deliberately not being polled — the post is gone, private, or the
    #: creator has to reconnect. Reversible via `resume()` once whatever
    #: caused it is fixed.
    stopped = "stopped"
    #: Failed too many times in a row for reasons we couldn't classify.
    #: Needs a human to look before it moves again.
    dead_lettered = "dead_lettered"


@dataclass(frozen=True)
class CadenceTier:
    """Posts younger than `max_age` are polled every `interval`."""

    max_age: timedelta
    interval: timedelta


#: First day at half-hourly resolution, first week every two hours, then
#: twice a day. Numbers chosen to be *defensible*, not optimal — Stage 3
#: has no production traffic to tune against, and D16 tracks revisiting
#: them once real campaigns are running.
DEFAULT_CADENCE: tuple[CadenceTier, ...] = (
    CadenceTier(max_age=timedelta(hours=24), interval=timedelta(minutes=30)),
    CadenceTier(max_age=timedelta(days=7), interval=timedelta(hours=2)),
    CadenceTier(max_age=timedelta(days=30), interval=timedelta(hours=12)),
)

#: Past this, a post is treated as finished and tracking stops. Campaigns
#: have end dates, but those live in Koded's domain — until his module can
#: tell us "this one's done", an age cap is what stops us polling a
#: year-old video forever.
TRACKING_WINDOW = timedelta(days=30)

#: Transient-failure backoff: 1, 2, 4, 8… minutes, capped.
RETRY_BASE = timedelta(minutes=1)
RETRY_CAP = timedelta(hours=1)

#: Consecutive unexplained failures before a submission is dead-lettered.
#: Six with the backoff above is roughly two hours of trying.
MAX_CONSECUTIVE_FAILURES = 6


def interval_for_age(age: timedelta, cadence: tuple[CadenceTier, ...] = DEFAULT_CADENCE) -> timedelta | None:
    """The polling interval for a post of this age, or None when it has
    aged out of the tracking window entirely."""
    for tier in cadence:
        if age < tier.max_age:
            return tier.interval
    return None


def backoff_delay(consecutive_failures: int) -> timedelta:
    """Exponential, capped, and never zero — `consecutive_failures` is the
    count *including* the failure being handled."""
    exponent = max(consecutive_failures - 1, 0)
    # Stop doubling well before the multiplication gets silly.
    if exponent > 16:
        return RETRY_CAP
    return min(RETRY_BASE * (2**exponent), RETRY_CAP)


class FailureAction(str, enum.Enum):
    retry = "retry"
    stop = "stop"
    dead_letter = "dead_letter"


@dataclass(frozen=True)
class FailureDecision:
    action: FailureAction
    #: How long to wait before the next attempt. Only set for `retry`.
    delay: timedelta | None
    #: Stable identifier for logs, metrics and the product surface —
    #: something a support person can be told to look for.
    code: str
    message: str


#: Failures the platform is telling us are permanent for this submission.
#: Retrying spends quota to be told the same thing, so we stop and let the
#: product decide what the creator sees.
_TERMINAL: dict[type[Exception], tuple[str, str]] = {
    ContentNotFound: ("content_not_found", "The post no longer resolves on the platform."),
    ContentUnavailable: (
        "content_unavailable",
        "The post is private, deleted, geo-blocked, or not this creator's.",
    ),
    CreatorTokenExpired: (
        "creator_reconnect_required",
        "The creator's platform token is dead; they must reconnect the account.",
    ),
    MissingCreatorToken: (
        "creator_reconnect_required",
        "No usable platform token for this creator; they must connect the account.",
    ),
    CapabilityNotSupported: (
        "capability_not_supported",
        "This platform can't answer the question being asked of it.",
    ),
    UrlNotRecognized: ("url_not_recognised", "The submitted URL isn't a readable post URL."),
}


def decide(error: Exception, *, consecutive_failures: int) -> FailureDecision:
    """Turn a failed poll into the next move.

    Order matters: the terminal lookup is exact-type, so it runs before the
    `isinstance` checks below and a subclass can't be silently swallowed by
    a parent's rule.
    """
    terminal = _TERMINAL.get(type(error))
    if terminal is not None:
        code, message = terminal
        return FailureDecision(FailureAction.stop, None, code, message)

    if isinstance(error, RateLimited):
        # Honour the provider's own number when it gives one — guessing
        # shorter is how a throttle turns into a ban.
        delay = (
            timedelta(seconds=error.retry_after)
            if error.retry_after
            else backoff_delay(consecutive_failures)
        )
        return FailureDecision(
            FailureAction.retry, delay, "rate_limited", f"Provider throttled us: {error}"
        )

    if isinstance(error, (UpstreamError, TokenLookupFailed)):
        return _retry_or_dead_letter(
            consecutive_failures,
            "upstream_error",
            f"Upstream failure, probably transient: {error}",
        )

    if isinstance(error, AdapterError):
        # An adapter error we haven't classified. Treat it as transient so
        # a new failure mode degrades into retries rather than silently
        # killing tracking, but let it dead-letter so it gets noticed.
        return _retry_or_dead_letter(
            consecutive_failures, "unclassified_adapter_error", f"Unhandled adapter error: {error}"
        )

    return _retry_or_dead_letter(
        consecutive_failures, "unexpected_error", f"{type(error).__name__}: {error}"
    )


def _retry_or_dead_letter(consecutive_failures: int, code: str, message: str) -> FailureDecision:
    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        return FailureDecision(
            FailureAction.dead_letter,
            None,
            code,
            f"{message} (gave up after {consecutive_failures} consecutive failures)",
        )
    return FailureDecision(
        FailureAction.retry, backoff_delay(consecutive_failures), code, message
    )
