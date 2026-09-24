"""Fixture tests for Instagram, Facebook, Threads, and X adapters."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from core.platforms import Platform
from integrations.social import get_adapter
from integrations.social.base import ContentKind, PostType, SocialPlatformAdapter
from integrations.social.facebook import FacebookAdapter
from integrations.social.instagram import InstagramAdapter
from integrations.social.threads import ThreadsAdapter
from integrations.social.x import XAdapter

ROOT = Path(__file__).parents[2] / "fixtures"
TOKEN = "test-token"


def fx(*parts: str) -> dict:
    return json.loads((ROOT.joinpath(*parts)).read_text())


def route_adapter(cls, routes: dict[str, tuple[int, dict]], **kwargs):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        full = str(request.url)
        for suffix, (status, payload) in routes.items():
            if path.rstrip("/").endswith(suffix):
                return httpx.Response(status, json=payload)
        return httpx.Response(404, json={"error": {"message": f"unmocked {path}"}})

    return cls(transport=httpx.MockTransport(handler), **kwargs)


async def test_instagram_resolve_and_metrics() -> None:
    media = fx("instagram", "media_ok.json")
    adapter = route_adapter(
        InstagramAdapter,
        {
            "/17900000000000001": (200, media),
            "/insights": (200, fx("instagram", "insights_ok.json")),
        },
    )
    assert await adapter.resolve_url("https://www.instagram.com/reel/AbCdefGhijk/") == "AbCdefGhijk"
    metrics = await adapter.get_metrics("17900000000000001", access_token=TOKEN)
    assert metrics.likes == 420
    assert metrics.views == 9800
    content = await adapter.get_content("17900000000000001", access_token=TOKEN)
    assert content.kind is ContentKind.video
    assert content.author_username == "adam.lawal"


async def test_instagram_comments() -> None:
    adapter = route_adapter(
        InstagramAdapter,
        {
            "/17900000000000001": (200, fx("instagram", "media_ok.json")),
            "/comments": (200, fx("instagram", "comments_ok.json")),
        },
    )
    page = await adapter.get_comments("17900000000000001", access_token=TOKEN)
    assert page.comments[0].text == "Fire fit"


async def test_facebook_resolve_posts_url() -> None:
    adapter = FacebookAdapter()
    assert await adapter.resolve_url("https://www.facebook.com/clippit/posts/222") == "222"
    assert (
        await adapter.resolve_url("https://www.facebook.com/permalink.php?story_fbid=222&id=111")
        == "111_222"
    )


async def test_facebook_metrics_and_comments() -> None:
    adapter = route_adapter(
        FacebookAdapter,
        {
            "/111_222": (200, fx("facebook", "post_ok.json")),
            "/insights": (
                200,
                {
                    "data": [
                        {"name": "post_video_views", "values": [{"value": 3200}]},
                        {"name": "post_impressions", "values": [{"value": 9000}]},
                        {"name": "post_impressions_unique", "values": [{"value": 4100}]},
                    ]
                },
            ),
            "/comments": (200, fx("facebook", "comments_ok.json")),
        },
    )
    metrics = await adapter.get_metrics("111_222", access_token=TOKEN)
    assert metrics.likes == 50
    assert metrics.comments == 7
    assert metrics.views == 3200
    assert metrics.impressions == 9000
    page = await adapter.get_comments("111_222", access_token=TOKEN)
    assert page.comments[0].author_username == "Ada"


async def test_threads_metrics() -> None:
    adapter = route_adapter(
        ThreadsAdapter,
        {
            "/17880000000000001": (200, fx("threads", "thread_ok.json")),
            "/insights": (200, fx("threads", "insights_ok.json")),
        },
    )
    assert await adapter.resolve_url("https://www.threads.net/@adam/post/Shortcode1") == "Shortcode1"
    metrics = await adapter.get_metrics("17880000000000001", access_token=TOKEN)
    assert metrics.views == 1200
    assert metrics.likes == 80
    assert metrics.comments == 9


async def test_x_resolve_and_metrics() -> None:
    adapter = XAdapter(
        api_key="k",
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=fx("x", "tweet_ok.json"))),
    )
    tweet_id = "1976592797731082295"
    assert await adapter.resolve_url(f"https://x.com/adam__lawal/status/{tweet_id}") == tweet_id
    metrics = await adapter.get_metrics(tweet_id)
    assert metrics.views == 1500
    content = await adapter.get_content(tweet_id)
    assert content.post_type is PostType.original
    assert content.author_username == "adam__lawal"


async def test_x_classifies_a_repost() -> None:
    adapter = XAdapter(
        api_key="k",
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json=fx("x", "tweet_repost.json"))
        ),
    )
    content = await adapter.get_content("1976592797731082296")
    assert content.post_type is PostType.repost


async def test_x_comments() -> None:
    adapter = XAdapter(
        api_key="k",
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json=fx("x", "replies_ok.json"))
        ),
    )
    page = await adapter.get_comments("1976592797731082295")
    assert page.comments[0].text == "nice"


@pytest.mark.parametrize(
    "platform",
    [
        Platform.instagram,
        Platform.facebook,
        Platform.threads,
        Platform.x,
        Platform.tiktok,
        Platform.youtube,
    ],
)
def test_registry_has_every_mvp_adapter(platform: Platform) -> None:
    adapter = get_adapter(platform)
    assert isinstance(adapter, SocialPlatformAdapter)
    assert adapter.platform is platform
