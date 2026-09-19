"""Instagram adapter — Instagram Graph API v22 (Business/Creator login).

Reads one media object by id, or finds it by shortcode via `/me/media`.
Comment text is available, unlike TikTok's Display API.
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

GRAPH = "https://graph.instagram.com/v22.0"
MEDIA_FIELDS = (
    "id,caption,media_type,permalink,timestamp,like_count,comments_count,shortcode,username"
)
COMMENT_FIELDS = "id,text,username,timestamp,like_count"
HOSTS = {"instagram.com", "www.instagram.com"}
SHORTCODE_RE = re.compile(r"/(?:p|reel|tv)/([^/?#]+)")


class InstagramAdapter:
    platform = Platform.instagram
    source = "instagram.graph_api"
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
        match = SHORTCODE_RE.search(parsed.path)
        if match:
            return match.group(1)
        # Numeric Graph media ids sometimes appear in URLs.
        digits = re.search(r"/(\d{5,})/?", parsed.path)
        return digits.group(1) if digits else None

    async def get_content(self, content_id: str, *, access_token: str | None = None) -> PlatformContent:
        media = await self._fetch_media(content_id, access_token)
        return self._to_content(media)

    async def get_metrics(self, content_id: str, *, access_token: str | None = None) -> PlatformMetrics:
        media = await self._fetch_media(content_id, access_token)
        insights = await self._insights(media["id"], media.get("media_type") or "IMAGE", access_token)
        return self._to_metrics(media, insights)

    async def get_comments(
        self,
        content_id: str,
        *,
        access_token: str | None = None,
        cursor: str | None = None,
    ) -> CommentPage:
        media = await self._fetch_media(content_id, access_token)
        params: dict[str, Any] = {
            "fields": COMMENT_FIELDS,
            "access_token": access_token or "",
            "limit": 50,
        }
        if cursor:
            params["after"] = cursor
        async with self._client() as client:
            try:
                resp = await client.get(f"{GRAPH}/{media['id']}/comments", params=params)
            except httpx.HTTPError as exc:
                raise UpstreamError(f"Instagram comments request failed: {exc}") from exc
        payload = raise_for_graph(resp, platform="Instagram")
        comments = [
            PlatformComment(
                platform=Platform.instagram,
                platform_comment_id=str(row.get("id", "")),
                platform_content_id=str(media["id"]),
                text=row.get("text") or "",
                author_username=row.get("username"),
                likes=row.get("like_count"),
                created_at=_parse_ts(row.get("timestamp")),
                raw=row,
            )
            for row in payload.get("data") or []
        ]
        paging = (payload.get("paging") or {}).get("cursors") or {}
        next_cursor = paging.get("after")
        return CommentPage(comments=comments, next_cursor=next_cursor, has_more=bool(next_cursor))

    async def _fetch_media(self, content_id: str, access_token: str | None) -> dict[str, Any]:
        if not access_token:
            raise AdapterError("Instagram requires the creator's access token; none was supplied.")
        # Numeric ids can be fetched directly; shortcodes need a permalink scan.
        if content_id.isdigit():
            return await self._get_node(content_id, access_token)
        media = await self._find_by_shortcode(content_id, access_token)
        if media is None:
            raise ContentUnavailable(
                f"Instagram returned no media for {content_id}: deleted, private, "
                "or not owned by the connected creator."
            )
        return media

    async def _get_node(self, media_id: str, access_token: str) -> dict[str, Any]:
        async with self._client() as client:
            try:
                resp = await client.get(
                    f"{GRAPH}/{media_id}",
                    params={"fields": MEDIA_FIELDS, "access_token": access_token},
                )
            except httpx.HTTPError as exc:
                raise UpstreamError(f"Instagram request failed: {exc}") from exc
        payload = raise_for_graph(resp, platform="Instagram")
        if not payload.get("id"):
            raise ContentUnavailable(f"Instagram returned no media for id {media_id}.")
        return payload

    async def _find_by_shortcode(self, shortcode: str, access_token: str) -> dict[str, Any] | None:
        url = f"{GRAPH}/me/media"
        params: dict[str, Any] = {
            "fields": MEDIA_FIELDS,
            "limit": 50,
            "access_token": access_token,
        }
        async with self._client() as client:
            for _ in range(5):
                try:
                    resp = await client.get(url, params=params)
                except httpx.HTTPError as exc:
                    raise UpstreamError(f"Instagram request failed: {exc}") from exc
                payload = raise_for_graph(resp, platform="Instagram")
                for item in payload.get("data") or []:
                    permalink = item.get("permalink") or ""
                    if item.get("shortcode") == shortcode or f"/{shortcode}" in permalink:
                        return item
                next_url = (payload.get("paging") or {}).get("next")
                if not next_url:
                    return None
                url = next_url
                params = {}
        return None

    async def _insights(self, media_id: str, media_type: str, access_token: str | None) -> dict[str, int]:
        metrics = "views,reach,saved,shares"
        async with self._client() as client:
            try:
                resp = await client.get(
                    f"{GRAPH}/{media_id}/insights",
                    params={"metric": metrics, "access_token": access_token or ""},
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
    def _to_content(media: dict[str, Any]) -> PlatformContent:
        kind = {
            "VIDEO": ContentKind.video,
            "REEL": ContentKind.video,
            "IMAGE": ContentKind.image,
            "CAROUSEL_ALBUM": ContentKind.image,
        }.get(media.get("media_type") or "", ContentKind.unknown)
        return PlatformContent(
            platform=Platform.instagram,
            platform_content_id=str(media.get("id", "")),
            url=media.get("permalink") or "",
            author_username=media.get("username"),
            kind=kind,
            post_type=PostType.original,
            caption=media.get("caption"),
            published_at=_parse_ts(media.get("timestamp")),
            raw=media,
        )

    @staticmethod
    def _to_metrics(media: dict[str, Any], insights: dict[str, int]) -> PlatformMetrics:
        views = insights.get("views")
        return PlatformMetrics(
            platform=Platform.instagram,
            platform_content_id=str(media.get("id", "")),
            observed_at=datetime.now(timezone.utc),
            views=views,
            likes=media.get("like_count"),
            comments=media.get("comments_count"),
            shares=insights.get("shares"),
            saves=insights.get("saved"),
            reach=insights.get("reach"),
            impressions=None,
            raw={"media": media, "insights": insights},
        )


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
