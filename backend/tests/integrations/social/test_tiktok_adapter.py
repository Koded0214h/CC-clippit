"""TikTok adapter tests — no credentials, no network.

Every test drives the adapter through `httpx.MockTransport`, replaying the
recorded payloads in `tests/fixtures/tiktok/`. That's the whole point of
Stage 1's exit condition being reproducible: the mapping and the error
handling have to be provable without a live TikTok app, because sandbox
tokens expire and CI will never have one.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from core.platforms import Platform
from integrations.social import get_adapter
from integrations.social.base import (
    AdapterError,
    CapabilityNotSupported,
    ContentKind,
    ContentUnavailable,
    CreatorTokenExpired,
    PostType,
    RateLimited,
    SocialPlatformAdapter,
    UpstreamError,
)
from integrations.social.tiktok import TikTokAdapter

FIXTURES = Path(__file__).parents[2] / "fixtures" / "tiktok"
TOKEN = "act.exampleToken"
VIDEO_ID = "7391234567890123456"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def adapter_returning(payload: dict, *, status: int = 200, headers: dict | None = None) -> TikTokAdapter:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload, headers=headers)

    return TikTokAdapter(transport=httpx.MockTransport(handler))


# --- URL resolution ---------------------------------------------------------
@pytest.mark.parametrize(
    "url",
    [
        "https://www.tiktok.com/@adam.lawal/video/7391234567890123456",
        "https://www.tiktok.com/@adam.lawal/video/7391234567890123456?is_from_webapp=1&sender_device=pc",
        "https://m.tiktok.com/@adam.lawal/video/7391234567890123456/",
        "  https://tiktok.com/@adam.lawal/video/7391234567890123456  ",
    ],
)
async def test_resolve_url_extracts_the_video_id(url: str) -> None:
    adapter = TikTokAdapter()
    assert await adapter.resolve_url(url) == VIDEO_ID


@pytest.mark.parametrize(
    "url",
    [
        "https://x.com/adam__lawal/status/1976592797731082295",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.tiktok.com/@adam.lawal",  # a profile, not a post
        "not a url at all",
    ],
)
async def test_resolve_url_returns_none_for_anything_not_a_tiktok_post(url: str) -> None:
    """None rather than an exception: a dispatcher should be able to offer a
    URL to each adapter in turn without catching anything."""

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError(f"no HTTP request should be made for {url}")

    adapter = TikTokAdapter(transport=httpx.MockTransport(handler))
    assert await adapter.resolve_url(url) is None


async def test_resolve_url_follows_a_short_link() -> None:
    """`vm.tiktok.com/ZM…` carries no ID, so one redirect must be followed."""
    canonical = f"https://www.tiktok.com/@adam.lawal/video/{VIDEO_ID}"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "vm.tiktok.com":
            return httpx.Response(301, headers={"Location": canonical})
        return httpx.Response(200, text="<html></html>")

    adapter = TikTokAdapter(transport=httpx.MockTransport(handler))
    assert await adapter.resolve_url("https://vm.tiktok.com/ZMabc123/") == VIDEO_ID


async def test_resolve_url_reports_a_dead_short_link_as_upstream_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    adapter = TikTokAdapter(transport=httpx.MockTransport(handler))
    with pytest.raises(UpstreamError):
        await adapter.resolve_url("https://vm.tiktok.com/ZMabc123/")


# --- Request shape ----------------------------------------------------------
async def test_query_sends_the_request_tiktok_documents() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=fixture("video_query_ok"))

    adapter = TikTokAdapter(transport=httpx.MockTransport(handler))
    await adapter.get_metrics(VIDEO_ID, access_token=TOKEN)

    assert seen["method"] == "POST"
    assert str(seen["url"]).startswith("https://open.tiktokapis.com/v2/video/query/?fields=")
    assert seen["auth"] == f"Bearer {TOKEN}"
    assert seen["body"] == {"filters": {"video_ids": [VIDEO_ID]}}
    assert "view_count" in str(seen["url"])


# --- Normalization ----------------------------------------------------------
async def test_get_metrics_maps_the_counters() -> None:
    adapter = adapter_returning(fixture("video_query_ok"))
    metrics = await adapter.get_metrics(VIDEO_ID, access_token=TOKEN)

    assert metrics.platform is Platform.tiktok
    assert metrics.platform_content_id == VIDEO_ID
    assert metrics.views == 128400
    assert metrics.likes == 9120
    assert metrics.comments == 431
    assert metrics.shares == 288
    assert metrics.observed_at.tzinfo is timezone.utc


async def test_metrics_tiktok_does_not_report_stay_none_not_zero() -> None:
    """The invariant the whole pipeline rests on: absent != zero. A 0 here
    would make Stage 4's ratios lie and Stage 5 flag innocent creators."""
    adapter = adapter_returning(fixture("video_query_ok"))
    metrics = await adapter.get_metrics(VIDEO_ID, access_token=TOKEN)

    assert metrics.saves is None
    assert metrics.reach is None
    assert metrics.impressions is None


async def test_metrics_keep_the_raw_payload() -> None:
    adapter = adapter_returning(fixture("video_query_ok"))
    metrics = await adapter.get_metrics(VIDEO_ID, access_token=TOKEN)

    assert metrics.raw["is_aigc"] is False
    assert metrics.raw["duration"] == 34


async def test_get_content_maps_identity() -> None:
    adapter = adapter_returning(fixture("video_query_ok"))
    content = await adapter.get_content(VIDEO_ID, access_token=TOKEN)

    assert content.platform_content_id == VIDEO_ID
    assert content.url == f"https://www.tiktok.com/@adam.lawal/video/{VIDEO_ID}"
    # Handle comes from the share URL, so no second call to /v2/user/info/.
    assert content.author_username == "adam.lawal"
    assert content.kind is ContentKind.video
    assert content.post_type is PostType.original
    assert content.caption == "fit check at Balogun market #lagos #streetstyle"
    assert content.published_at == datetime.fromtimestamp(1789000000, tz=timezone.utc)


async def test_content_is_immutable() -> None:
    """Observations are historical facts; nothing downstream may edit one
    between fetching it and storing it."""
    adapter = adapter_returning(fixture("video_query_ok"))
    content = await adapter.get_content(VIDEO_ID, access_token=TOKEN)

    with pytest.raises(Exception):
        content.url = "https://example.com"  # type: ignore[misc]


# --- Failures ---------------------------------------------------------------
async def test_empty_result_is_content_unavailable_not_not_found() -> None:
    """TikTok returns `ok` with an empty list for deleted, private *and*
    someone-else's videos alike, so we must not claim it doesn't exist."""
    adapter = adapter_returning(fixture("video_query_empty"))
    with pytest.raises(ContentUnavailable):
        await adapter.get_metrics(VIDEO_ID, access_token=TOKEN)


async def test_api_error_code_beats_http_200() -> None:
    """TikTok answers HTTP 200 with `error.code` set, so status alone lies."""
    adapter = adapter_returning(fixture("error_access_token_invalid"))
    with pytest.raises(CreatorTokenExpired):
        await adapter.get_metrics(VIDEO_ID, access_token=TOKEN)


async def test_http_429_becomes_rate_limited_with_retry_after() -> None:
    adapter = adapter_returning({}, status=429, headers={"Retry-After": "30"})
    with pytest.raises(RateLimited) as caught:
        await adapter.get_metrics(VIDEO_ID, access_token=TOKEN)

    assert caught.value.retry_after == 30


async def test_x_ratelimit_reset_epoch_is_converted_to_a_duration() -> None:
    reset_at = int(time.time()) + 45
    adapter = adapter_returning({}, status=429, headers={"X-RateLimit-Reset": str(reset_at)})
    with pytest.raises(RateLimited) as caught:
        await adapter.get_metrics(VIDEO_ID, access_token=TOKEN)

    assert 40 <= (caught.value.retry_after or 0) <= 45


async def test_rate_limit_error_code_also_becomes_rate_limited() -> None:
    payload = {"error": {"code": "rate_limit_exceeded", "message": "too many requests"}}
    adapter = adapter_returning(payload)
    with pytest.raises(RateLimited):
        await adapter.get_metrics(VIDEO_ID, access_token=TOKEN)


async def test_401_becomes_creator_token_expired() -> None:
    adapter = adapter_returning({}, status=401)
    with pytest.raises(CreatorTokenExpired):
        await adapter.get_metrics(VIDEO_ID, access_token=TOKEN)


async def test_server_error_becomes_upstream_error() -> None:
    adapter = adapter_returning({}, status=503)
    with pytest.raises(UpstreamError):
        await adapter.get_metrics(VIDEO_ID, access_token=TOKEN)


async def test_non_json_body_becomes_upstream_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>502 Bad Gateway</html>")

    adapter = TikTokAdapter(transport=httpx.MockTransport(handler))
    with pytest.raises(UpstreamError):
        await adapter.get_metrics(VIDEO_ID, access_token=TOKEN)


async def test_invalid_params_is_our_bug_not_a_retryable_failure() -> None:
    payload = {"error": {"code": "invalid_params", "message": "field not supported"}}
    adapter = adapter_returning(payload)
    with pytest.raises(AdapterError) as caught:
        await adapter.get_metrics(VIDEO_ID, access_token=TOKEN)

    assert not isinstance(caught.value, (RateLimited, UpstreamError))


async def test_missing_token_fails_before_any_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("must not call TikTok without a token")

    adapter = TikTokAdapter(transport=httpx.MockTransport(handler))
    with pytest.raises(AdapterError):
        await adapter.get_metrics(VIDEO_ID, access_token=None)


async def test_batch_larger_than_twenty_is_rejected_locally() -> None:
    """TikTok caps a query at 20 ids; better to fail loudly than to have the
    Stage 3 batcher silently lose submissions off the end of a page."""
    adapter = TikTokAdapter()
    with pytest.raises(AdapterError):
        await adapter.query_videos([str(i) for i in range(21)], TOKEN)


async def test_comments_are_declared_unsupported() -> None:
    adapter = TikTokAdapter()
    assert adapter.supports_comments is False
    with pytest.raises(CapabilityNotSupported):
        await adapter.get_comments(VIDEO_ID, access_token=TOKEN)


# --- Wiring -----------------------------------------------------------------
def test_adapter_satisfies_the_protocol_and_is_registered() -> None:
    adapter = get_adapter(Platform.tiktok)

    assert isinstance(adapter, SocialPlatformAdapter)
    assert isinstance(adapter, TikTokAdapter)
    assert adapter.platform is Platform.tiktok
    assert adapter.requires_creator_token is True
