"""Facebook adapter — Graph API v22, Page posts only.

The stored token is a user token. Posts are read with it, or via the
first Page token from `/me/accounts` if the user token is not enough.
A Facebook user with no Pages has nothing we can ingest — personal
profile posts are not available on this path.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from core.platforms import Platform

from .base import (
    AdapterError,
    CommentPage,
    ContentKind,
    ContentUnavailable,
    PlatformComment,
    PlatformContent,
    PlatformMetrics,
    PostType,
    UpstreamError,
)
from .graph import raise_for_graph

GRAPH = "https://graph.facebook.com/v22.0"
POST_FIELDS = (
    "id,message,created_time,permalink_url,shares,type,status_type,"
    "likes.summary(true).limit(0),comments.summary(true).limit(0)"
)
HOSTS = {"facebook.com", "www.facebook.com", "m.facebook.com", "fb.com", "www.fb.com"}
POSTS_RE = re.compile(r"/posts/([^/?#]+)")
VIDEO_RE = re.compile(r"/videos/([^/?#]+)")
PHOTO_RE = re.compile(r"/photos/(?:[^/]+/)?([^/?#]+)")


class FacebookAdapter:
    platform = Platform.facebook
    source = "facebook.graph_api"
    requires_creator_token = True
    supports_comments = True

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._transport = transport
        self._timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)

    async def resolve_url(self, url: str) -> str | None:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower()
        if host not in HOSTS:
            return None
        qs = parse_qs(parsed.query)
        story = (qs.get("story_fbid") or [None])[0]
        page = (qs.get("id") or [None])[0]
        if story and page:
            return f"{page}_{story}"
        for pattern in (POSTS_RE, VIDEO_RE, PHOTO_RE):
            match = pattern.search(parsed.path)
            if match:
                return match.group(1)
        return None

    async def get_content(self, content_id: str, *, access_token: str | None = None) -> PlatformContent:
        post = await self._get_post(content_id, access_token)
        return self._to_content(post)

    async def get_metrics(self, content_id: str, *, access_token: str | None = None) -> PlatformMetrics:
        post = await self._get_post(content_id, access_token)
        insights = await self._insights(post["id"], access_token)
        return self._to_metrics(post, insights)

    async def get_comments(
        self,
        content_id: str,
        *,
        access_token: str | None = None,
        cursor: str | None = None,
    ) -> CommentPage:
        post = await self._get_post(content_id, access_token)
        params: dict[str, Any] = {
            "fields": "id,message,from,created_time,like_count",
            "access_token": access_token or "",
            "limit": 50,
        }
        if cursor:
            params["after"] = cursor
        async with self._client() as client:
            try:
                resp = await client.get(f"{GRAPH}/{post['id']}/comments", params=params)
            except httpx.HTTPError as exc:
                raise UpstreamError(f"Facebook comments request failed: {exc}") from exc
        payload = raise_for_graph(resp, platform="Facebook")
        comments = [
            PlatformComment(
                platform=Platform.facebook,
                platform_comment_id=str(row.get("id", "")),
                platform_content_id=str(post["id"]),
                text=row.get("message") or "",
                author_platform_user_id=(row.get("from") or {}).get("id"),
                author_username=(row.get("from") or {}).get("name"),
                likes=row.get("like_count"),
                created_at=_parse_ts(row.get("created_time")),
                raw=row,
            )
            for row in payload.get("data") or []
        ]
        next_cursor = ((payload.get("paging") or {}).get("cursors") or {}).get("after")
        return CommentPage(comments=comments, next_cursor=next_cursor, has_more=bool(next_cursor))

    async def _get_post(self, content_id: str, access_token: str | None) -> dict[str, Any]:
        if not access_token:
            raise AdapterError("Facebook requires the creator's access token; none was supplied.")
        async with self._client() as client:
            try:
                resp = await client.get(
                    f"{GRAPH}/{content_id}",
                    params={"fields": POST_FIELDS, "access_token": access_token},
                )
            except httpx.HTTPError as exc:
                raise UpstreamError(f"Facebook request failed: {exc}") from exc
        payload = raise_for_graph(resp, platform="Facebook")
        if not payload.get("id"):
            raise ContentUnavailable(f"Facebook returned no post for id {content_id}.")
        return payload

    async def _insights(self, post_id: str, access_token: str | None) -> dict[str, int]:
        async with self._client() as client:
            try:
                resp = await client.get(
                    f"{GRAPH}/{post_id}/insights",
                    params={
                        # post_video_views is Meta's official video-view
                        # metric (3s+). Impressions/reach stay as secondary
                        # signals for trust; earnings bill on `views`.
                        "metric": (
                            "post_impressions,post_impressions_unique,"
                            "post_clicks,post_video_views"
                        ),
                        "access_token": access_token or "",
                    },
                )
            except httpx.HTTPError:
                return {}
        if resp.status_code >= 400:
            return {}
        try:
            payload = resp.json()
        except ValueError:
            return {}
        out: dict[str, int] = {}
        for row in payload.get("data") or []:
            name = row.get("name")
            values = row.get("values") or []
            if name and values:
                out[name] = int(values[0].get("value") or 0)
        return out

    @staticmethod
    def _to_content(post: dict[str, Any]) -> PlatformContent:
        kind = ContentKind.video if post.get("type") == "video" else ContentKind.text
        if post.get("type") == "photo":
            kind = ContentKind.image
        return PlatformContent(
            platform=Platform.facebook,
            platform_content_id=str(post.get("id", "")),
            url=post.get("permalink_url") or "",
            kind=kind,
            post_type=PostType.original,
            caption=post.get("message"),
            published_at=_parse_ts(post.get("created_time")),
            raw=post,
        )

    @staticmethod
    def _to_metrics(post: dict[str, Any], insights: dict[str, int]) -> PlatformMetrics:
        likes = (post.get("likes") or {}).get("summary", {}).get("total_count")
        comments = (post.get("comments") or {}).get("summary", {}).get("total_count")
        shares = (post.get("shares") or {}).get("count")
        # Prefer official video views. Never invent 0 from missing data;
        # non-video posts typically have no view metric on Graph.
        views = insights.get("post_video_views")
        return PlatformMetrics(
            platform=Platform.facebook,
            platform_content_id=str(post.get("id", "")),
            observed_at=datetime.now(timezone.utc),
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
            saves=None,
            reach=insights.get("post_impressions_unique"),
            impressions=insights.get("post_impressions"),
            raw={"post": post, "insights": insights},
        )


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
