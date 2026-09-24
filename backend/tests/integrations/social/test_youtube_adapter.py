"""Fixture tests for the YouTube Data API adapter."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from core.platforms import Platform, V1_PLATFORMS, is_v1_platform
from integrations.social import get_adapter
from integrations.social.base import ContentKind, ContentNotFound, SocialPlatformAdapter
from integrations.social.youtube import YouTubeAdapter

ROOT = Path(__file__).parents[2] / "fixtures"


def fx(*parts: str) -> dict:
    return json.loads((ROOT.joinpath(*parts)).read_text())


def route_adapter(routes: dict[str, tuple[int, dict]], **kwargs) -> YouTubeAdapter:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        for suffix, (status, payload) in routes.items():
            if path.rstrip("/").endswith(suffix):
                return httpx.Response(status, json=payload)
        return httpx.Response(404, json={"error": {"message": f"unmocked {path}"}})

    return YouTubeAdapter(api_key="test-key", transport=httpx.MockTransport(handler), **kwargs)


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://example.com/watch?v=dQw4w9WgXcQ", None),
    ],
)
async def test_youtube_resolve_url(url: str, expected: str | None) -> None:
    adapter = YouTubeAdapter(api_key="k")
    assert await adapter.resolve_url(url) == expected


async def test_youtube_metrics_and_content() -> None:
    adapter = route_adapter({"/videos": (200, fx("youtube", "video_ok.json"))})
    metrics = await adapter.get_metrics("dQw4w9WgXcQ")
    assert metrics.views == 12500
    assert metrics.likes == 840
    assert metrics.comments == 62
    content = await adapter.get_content("dQw4w9WgXcQ")
    assert content.kind is ContentKind.video
    assert content.author_platform_user_id == "UCclippitchannel01"
    assert content.author_username == "Clippit Creator"


async def test_youtube_missing_video() -> None:
    adapter = route_adapter({"/videos": (200, fx("youtube", "video_empty.json"))})
    with pytest.raises(ContentNotFound):
        await adapter.get_metrics("dQw4w9WgXcQ")


async def test_youtube_comments() -> None:
    adapter = route_adapter({"/commentThreads": (200, fx("youtube", "comments_ok.json"))})
    page = await adapter.get_comments("dQw4w9WgXcQ")
    assert page.comments[0].text == "Fire edit"
    assert page.comments[0].author_username == "Ada"


def test_registry_includes_youtube() -> None:
    adapter = get_adapter(Platform.youtube)
    assert isinstance(adapter, SocialPlatformAdapter)
    assert adapter.platform is Platform.youtube
    assert adapter.requires_creator_token is False
    assert adapter.supports_comments is True


def test_v1_platforms_match_prd() -> None:
    assert Platform.youtube in V1_PLATFORMS
    assert Platform.threads not in V1_PLATFORMS
    assert is_v1_platform("youtube")
    assert not is_v1_platform(Platform.threads)
