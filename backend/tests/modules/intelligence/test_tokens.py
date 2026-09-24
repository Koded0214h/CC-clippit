"""The seam between this module and Auth & Accounts.

Every one of auth's documented responses is pinned here, because the
distinction they encode is the one that matters operationally: "the
creator must reconnect" (don't retry, tell the product) versus "our
plumbing is broken" (retry, page someone).
"""

from __future__ import annotations

import uuid

import httpx
import pytest

from core.platforms import Platform
from modules.intelligence.errors import MissingCreatorToken, TokenLookupFailed
from modules.intelligence.tokens import InternalApiTokenSource

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _source(handler) -> InternalApiTokenSource:
    return InternalApiTokenSource(
        base_url="http://auth.test",
        secret="shhh",
        transport=httpx.MockTransport(handler),
    )


async def test_returns_the_token_and_calls_the_documented_route():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["secret"] = request.headers.get("X-Internal-Secret", "")
        return httpx.Response(
            200,
            json={"access_token": "act.123", "platform_user_id": "u-9", "expires_at": None},
        )

    token = await _source(handler).token_for(CREATOR_ID, Platform.tiktok)

    assert token == "act.123"
    assert seen["url"] == f"http://auth.test/internal/social-accounts/{CREATOR_ID}/tiktok/token"
    assert seen["secret"] == "shhh"


async def test_credential_for_includes_platform_user_id():
    source = _source(
        lambda request: httpx.Response(
            200,
            json={
                "access_token": "act.yt",
                "platform_user_id": "UCchannel",
                "expires_at": None,
            },
        )
    )
    cred = await source.credential_for(CREATOR_ID, Platform.youtube)
    assert cred.access_token == "act.yt"
    assert cred.platform_user_id == "UCchannel"


@pytest.mark.parametrize("status", [404, 409])
async def test_creator_problems_are_not_retryable(status):
    """404: never connected. 409: expired beyond refresh. Either way the
    creator has to act, so a retry loop would only waste calls."""
    source = _source(lambda request: httpx.Response(status, json={"detail": "nope"}))

    with pytest.raises(MissingCreatorToken):
        await source.token_for(CREATOR_ID, Platform.tiktok)


async def test_an_empty_token_is_treated_as_missing():
    source = _source(lambda request: httpx.Response(200, json={"access_token": ""}))

    with pytest.raises(MissingCreatorToken):
        await source.token_for(CREATOR_ID, Platform.tiktok)


async def test_a_rejected_internal_secret_is_our_problem_not_the_creators():
    source = _source(lambda request: httpx.Response(401, json={"detail": "Invalid"}))

    with pytest.raises(TokenLookupFailed):
        await source.token_for(CREATOR_ID, Platform.tiktok)


async def test_a_platform_auth_does_not_know_points_at_decision_d5():
    """Auth's `platform` enum holds four values; ours holds six. Asking for
    X today gets a 422, and the error has to say why."""
    source = _source(lambda request: httpx.Response(422, json={"detail": "bad enum"}))

    with pytest.raises(TokenLookupFailed, match="D5"):
        await source.token_for(CREATOR_ID, Platform.x)


async def test_an_unreachable_auth_module_is_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(TokenLookupFailed):
        await _source(handler).token_for(CREATOR_ID, Platform.tiktok)
