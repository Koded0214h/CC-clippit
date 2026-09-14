"""The polling policy, checked as a table of rules.

These are pure functions, so this file is the cheap place to pin down
every judgement call — cadence tiers, backoff growth, and which
exceptions mean "wait", "give up on this post", or "wake a human". The
worker tests then only have to prove the decisions are *applied*.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from integrations.social.base import (
    AdapterError,
    CapabilityNotSupported,
    ContentNotFound,
    ContentUnavailable,
    CreatorTokenExpired,
    RateLimited,
    UpstreamError,
)
from modules.intelligence.errors import MissingCreatorToken, TokenLookupFailed, UrlNotRecognized
from modules.intelligence.scheduling import (
    MAX_CONSECUTIVE_FAILURES,
    RETRY_CAP,
    FailureAction,
    backoff_delay,
    decide,
    interval_for_age,
)


@pytest.mark.parametrize(
    "age, expected",
    [
        (timedelta(minutes=5), timedelta(minutes=30)),
        (timedelta(hours=23), timedelta(minutes=30)),
        (timedelta(hours=25), timedelta(hours=2)),
        (timedelta(days=6), timedelta(hours=2)),
        (timedelta(days=8), timedelta(hours=12)),
        (timedelta(days=29), timedelta(hours=12)),
    ],
)
def test_cadence_widens_as_a_post_ages(age, expected):
    assert interval_for_age(age) == expected


def test_a_post_past_the_tracking_window_stops_being_polled():
    assert interval_for_age(timedelta(days=31)) is None


def test_backoff_doubles_and_then_stops_growing():
    delays = [backoff_delay(n) for n in range(1, 5)]
    assert delays == [
        timedelta(minutes=1),
        timedelta(minutes=2),
        timedelta(minutes=4),
        timedelta(minutes=8),
    ]
    assert backoff_delay(50) == RETRY_CAP, "a long outage must not schedule a retry in 3024 years"


@pytest.mark.parametrize(
    "error, code",
    [
        (ContentNotFound("gone"), "content_not_found"),
        (ContentUnavailable("private"), "content_unavailable"),
        (CreatorTokenExpired("dead"), "creator_reconnect_required"),
        (MissingCreatorToken("never connected"), "creator_reconnect_required"),
        (CapabilityNotSupported("no comments"), "capability_not_supported"),
        (UrlNotRecognized("profile link"), "url_not_recognised"),
    ],
)
def test_permanent_problems_stop_polling_immediately(error, code):
    """Retrying these spends rate limit to be told the same thing."""
    decision = decide(error, consecutive_failures=1)

    assert decision.action is FailureAction.stop
    assert decision.code == code


def test_rate_limiting_honours_the_providers_own_retry_after():
    decision = decide(RateLimited("slow down", retry_after=90), consecutive_failures=1)

    assert decision.action is FailureAction.retry
    assert decision.delay == timedelta(seconds=90)


def test_rate_limiting_without_a_header_falls_back_to_backoff():
    decision = decide(RateLimited("slow down"), consecutive_failures=3)

    assert decision.action is FailureAction.retry
    assert decision.delay == backoff_delay(3)


@pytest.mark.parametrize(
    "error",
    [UpstreamError("502"), TokenLookupFailed("auth unreachable"), RuntimeError("who knows")],
)
def test_transient_problems_retry_then_dead_letter(error):
    assert decide(error, consecutive_failures=1).action is FailureAction.retry
    assert (
        decide(error, consecutive_failures=MAX_CONSECUTIVE_FAILURES).action
        is FailureAction.dead_letter
    )


def test_an_unclassified_adapter_error_degrades_to_retrying_not_to_silence():
    """A failure mode we haven't met yet should slow down and get noticed,
    never quietly stop tracking a submission."""

    class NewAdapterProblem(AdapterError):
        pass

    decision = decide(NewAdapterProblem("something new"), consecutive_failures=1)

    assert decision.action is FailureAction.retry
    assert decision.code == "unclassified_adapter_error"


def test_every_decision_carries_a_stable_code_and_a_readable_message():
    """Codes get logged and surfaced; messages get read by whoever is
    trying to work out what happened at 2am."""
    for error in (ContentNotFound("x"), RateLimited("y"), UpstreamError("z")):
        decision = decide(error, consecutive_failures=1)
        assert decision.code and decision.code.islower()
        assert decision.message
