"""Threads adapter — Threads Graph API v1.0.

Insights live on a sibling `/insights` call. Replies are the comment
text Stage 6 samples. `is_quote_status` is not requested on GET /{id} —
that field 500s there even though `/me/threads` accepts it.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

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

GRAPH = "https://graph.threads.net/v1.0"
# `is_quote_status` is valid on /me/threads but 500s on GET /{id}.
THREAD_FIELDS = "id,text,media_type,permalink,timestamp,shortcode,username"
INSIGHT_METRICS = "views,likes,replies,reposts,quotes"
HOSTS = {"threads.net", "www.threads.net", "threads.com", "www.threads.com"}
POST_RE = re.compile(r"/post/([^/?#]+)")


class ThreadsAdapter:
    platform = Platform.threads
    source = "threads.graph_api"
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
        match = POST_RE.search(parsed.path)
        return match.group(1) if match else None

    async def get_content(self, content_id: str, *, access_token: str | None = None) -> PlatformContent:
        item = await self._fetch(content_id, access_token)
        return self._to_content(item)

    async def get_metrics(self, content_id: str, *, access_token: str | None = None) -> PlatformMetrics:
        item = await self._fetch(content_id, access_token)
        insights = await self._insights(item["id"], access_token)
        return self._to_metrics(item, insights)

    async def get_comments(
        self,
        content_id: str,
        *,
        access_token: str | None = None,
        cursor: str | None = None,
    ) -> CommentPage:
        item = await self._fetch(content_id, access_token)
        params: dict[str, Any] = {
            "fields": "id,text,username,timestamp",
            "access_token": access_token or "",
            "limit": 50,
        }
        if cursor:
            params["after"] = cursor
        async with self._client() as client:
            try:
                resp = await client.get(f"{GRAPH}/{item['id']}/replies", params=params)
            except httpx.HTTPError as exc:
                raise UpstreamError(f"Threads replies request failed: {exc}") from exc
        payload = raise_for_graph(resp, platform="Threads")
        comments = [
            PlatformComment(
                platform=Platform.threads,
                platform_comment_id=str(row.get("id", "")),
                platform_content_id=str(item["id"]),
                text=row.get("text") or "",
                author_username=row.get("username"),
                created_at=_parse_ts(row.get("timestamp")),
                raw=row,
            )
            for row in payload.get("data") or []
        ]
        next_cursor = ((payload.get("paging") or {}).get("cursors") or {}).get("after")
        return CommentPage(comments=comments, next_cursor=next_cursor, has_more=bool(next_cursor))

    async def _fetch(self, content_id: str, access_token: str | None) -> dict[str, Any]:
        if not access_token:
            raise AdapterError("Threads requires the creator's access token; none was supplied.")
        # Shortcodes 400 on GET /{id}; only numeric Graph ids are addressable.
        if content_id.isdigit():
            node = await self._get_node(content_id, access_token)
            if node:
                return node
        found = await self._find_by_shortcode(content_id, access_token)
        if found is None:
            raise ContentUnavailable(
                f"Threads returned no post for {content_id}: deleted, private, "
                "or not owned by the connected creator."
            )
        return found

    async def _get_node(self, media_id: str, access_token: str) -> dict[str, Any] | None:
        async with self._client() as client:
            try:
                resp = await client.get(
                    f"{GRAPH}/{media_id}",
                    params={"fields": THREAD_FIELDS, "access_token": access_token},
                )
            except httpx.HTTPError as exc:
                raise UpstreamError(f"Threads request failed: {exc}") from exc
        if resp.status_code >= 400:
            return None
        payload = raise_for_graph(resp, platform="Threads")
        return payload if payload.get("id") else None

    async def _find_by_shortcode(self, shortcode: str, access_token: str) -> dict[str, Any] | None:
        url = f"{GRAPH}/me/threads"
        params: dict[str, Any] = {
            "fields": THREAD_FIELDS,
            "limit": 50,
            "access_token": access_token,
        }
        async with self._client() as client:
            for _ in range(5):
                try:
                    resp = await client.get(url, params=params)
                except httpx.HTTPError as exc:
                    raise UpstreamError(f"Threads request failed: {exc}") from exc
                payload = raise_for_graph(resp, platform="Threads")
                for item in payload.get("data") or []:
                    permalink = item.get("permalink") or ""
                    if (
                        str(item.get("id") or "") == shortcode
                        or item.get("shortcode") == shortcode
                        or f"/post/{shortcode}" in permalink
                    ):
                        return item
                next_url = (payload.get("paging") or {}).get("next")
                if not next_url:
                    return None
                url = next_url
                params = {}
        return None

    async def _insights(self, media_id: str, access_token: str | None) -> dict[str, int]:
        async with self._client() as client:
            try:
                resp = await client.get(
                    f"{GRAPH}/{media_id}/insights",
                    params={"metric": INSIGHT_METRICS, "access_token": access_token or ""},
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
    def _to_content(item: dict[str, Any]) -> PlatformContent:
        post_type = PostType.quote if item.get("is_quote_status") else PostType.original
        media_type = item.get("media_type") or "TEXT"
        kind = ContentKind.video if media_type in {"VIDEO", "REEL"} else ContentKind.text
        if media_type in {"IMAGE", "CAROUSEL_ALBUM"}:
            kind = ContentKind.image
        return PlatformContent(
            platform=Platform.threads,
            platform_content_id=str(item.get("id", "")),
            url=item.get("permalink") or "",
            author_username=item.get("username"),
            kind=kind,
            post_type=post_type,
            caption=item.get("text"),
            published_at=_parse_ts(item.get("timestamp")),
            raw=item,
        )

    @staticmethod
    def _to_metrics(item: dict[str, Any], insights: dict[str, int]) -> PlatformMetrics:
        return PlatformMetrics(
            platform=Platform.threads,
            platform_content_id=str(item.get("id", "")),
            observed_at=datetime.now(timezone.utc),
            views=insights.get("views"),
            likes=insights.get("likes"),
            comments=insights.get("replies"),
            shares=insights.get("reposts"),
            saves=None,
            reach=None,
            impressions=None,
            raw={"thread": item, "insights": insights},
        )


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
