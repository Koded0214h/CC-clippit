"""YouTube adapter — Data API v3 for metrics; OAuth identity lives in auth.

Public video stats are readable with `YOUTUBE_API_KEY` (same pattern as X /
twitterapi.io). Creators still connect via OAuth so Core knows *who*
submitted and Intelligence can verify channel ownership on first ingest.

Accepted URL shapes: watch?v=, youtu.be/, /shorts/, /embed/, /live/.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from core.config import get_settings
from core.platforms import Platform

from .base import (
    AdapterError,
    CommentPage,
    ContentKind,
    ContentNotFound,
    ContentUnavailable,
    CreatorTokenExpired,
    PlatformComment,
    PlatformContent,
    PlatformMetrics,
    PostType,
    RateLimited,
    UpstreamError,
)

API_BASE = "https://www.googleapis.com/youtube/v3"
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


class YouTubeAdapter:
    platform = Platform.youtube
    source = "youtube.data_api"
    #: Metrics use YOUTUBE_API_KEY. Submissions still require a connected
    #: YouTube account at the Core layer; ownership is checked on ingest.
    requires_creator_token = False
    supports_comments = True

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 20.0,
    ) -> None:
        self._api_key = api_key
        self._transport = transport
        self._timeout = timeout

    def _key(self) -> str:
        key = self._api_key if self._api_key is not None else get_settings().youtube_api_key
        if not key:
            raise AdapterError("YOUTUBE_API_KEY is not configured.")
        return key

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)

    async def resolve_url(self, url: str) -> str | None:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower()
        if host not in HOSTS:
            return None

        if host in {"youtu.be", "www.youtu.be"}:
            candidate = parsed.path.lstrip("/").split("/")[0]
            return candidate if VIDEO_ID_RE.match(candidate or "") else None

        qs = parse_qs(parsed.query)
        if "v" in qs and qs["v"] and VIDEO_ID_RE.match(qs["v"][0]):
            return qs["v"][0]

        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live", "v"}:
            candidate = parts[1]
            return candidate if VIDEO_ID_RE.match(candidate) else None
        return None

    async def get_content(self, content_id: str, *, access_token: str | None = None) -> PlatformContent:
        video = await self._video(content_id)
        return self._to_content(video)

    async def get_metrics(self, content_id: str, *, access_token: str | None = None) -> PlatformMetrics:
        video = await self._video(content_id)
        return self._to_metrics(video)

    async def get_comments(
        self,
        content_id: str,
        *,
        access_token: str | None = None,
        cursor: str | None = None,
    ) -> CommentPage:
        params: dict[str, Any] = {
            "part": "snippet",
            "videoId": content_id,
            "maxResults": 50,
            "textFormat": "plainText",
            "key": self._key(),
        }
        if cursor:
            params["pageToken"] = cursor
        payload = await self._api_get("/commentThreads", params)
        comments: list[PlatformComment] = []
        for row in payload.get("items") or []:
            top = ((row.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
            comments.append(
                PlatformComment(
                    platform=Platform.youtube,
                    platform_comment_id=str(
                        ((row.get("snippet") or {}).get("topLevelComment") or {}).get("id")
                        or row.get("id")
                        or ""
                    ),
                    platform_content_id=content_id,
                    text=top.get("textDisplay") or top.get("textOriginal") or "",
                    author_platform_user_id=top.get("authorChannelId", {}).get("value")
                    if isinstance(top.get("authorChannelId"), dict)
                    else None,
                    author_username=top.get("authorDisplayName"),
                    likes=top.get("likeCount"),
                    replies=(row.get("snippet") or {}).get("totalReplyCount"),
                    created_at=_parse_ts(top.get("publishedAt")),
                    raw=row,
                )
            )
        next_cursor = payload.get("nextPageToken")
        return CommentPage(
            comments=comments,
            next_cursor=next_cursor,
            has_more=bool(next_cursor),
        )

    async def _video(self, video_id: str) -> dict[str, Any]:
        payload = await self._api_get(
            "/videos",
            {
                "part": "snippet,statistics,contentDetails,status",
                "id": video_id,
                "key": self._key(),
            },
        )
        items = payload.get("items") or []
        if not items:
            raise ContentNotFound(f"YouTube returned no video for id {video_id}.")
        return items[0]

    async def _api_get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            async with self._client() as client:
                resp = await client.get(f"{API_BASE}{path}", params=params)
        except httpx.HTTPError as exc:
            raise UpstreamError(f"YouTube Data API request failed: {exc}") from exc

        try:
            payload = resp.json()
        except ValueError as exc:
            raise UpstreamError("YouTube Data API returned a non-JSON body.") from exc

        if resp.status_code == 429:
            retry = resp.headers.get("Retry-After")
            raise RateLimited(
                "YouTube Data API quota / rate limit hit.",
                retry_after=int(retry) if retry and str(retry).isdigit() else None,
            )
        if resp.status_code >= 400:
            reason = _first_reason(payload) or "unknown"
            message = ((payload.get("error") or {}).get("message")) or f"HTTP {resp.status_code}"
            if reason in {"commentsDisabled", "processingFailure"}:
                raise ContentUnavailable(f"YouTube comments unavailable ({reason}).")
            if reason in {"videoNotFound", "playlistNotFound"}:
                raise ContentNotFound(f"YouTube resource not found ({reason}).")
            if reason in {"API_KEY_INVALID", "badRequest"} or resp.status_code in (401, 403):
                raise CreatorTokenExpired(
                    f"YouTube Data API rejected the key/request: {message} ({reason}). "
                    "Check YOUTUBE_API_KEY and that YouTube Data API v3 is enabled."
                )
            if resp.status_code >= 500:
                raise UpstreamError(f"YouTube Data API returned HTTP {resp.status_code}: {message}")
            raise UpstreamError(f"YouTube Data API error: {message} ({reason})")
        return payload

    @staticmethod
    def _to_content(video: dict[str, Any]) -> PlatformContent:
        snippet = video.get("snippet") or {}
        video_id = str(video.get("id", ""))
        return PlatformContent(
            platform=Platform.youtube,
            platform_content_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
            author_platform_user_id=snippet.get("channelId"),
            author_username=snippet.get("channelTitle"),
            kind=ContentKind.video,
            post_type=PostType.original,
            caption=snippet.get("title") or snippet.get("description"),
            published_at=_parse_ts(snippet.get("publishedAt")),
            raw=video,
        )

    @staticmethod
    def _to_metrics(video: dict[str, Any]) -> PlatformMetrics:
        stats = video.get("statistics") or {}
        return PlatformMetrics(
            platform=Platform.youtube,
            platform_content_id=str(video.get("id", "")),
            observed_at=datetime.now(timezone.utc),
            views=_int_or_none(stats.get("viewCount")),
            likes=_int_or_none(stats.get("likeCount")),
            comments=_int_or_none(stats.get("commentCount")),
            shares=None,
            saves=None,
            reach=None,
            impressions=None,
            raw=video,
        )


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _first_reason(body: dict[str, Any]) -> str | None:
    errors = ((body.get("error") or {}).get("errors")) or []
    if errors and isinstance(errors[0], dict):
        return errors[0].get("reason")
    return None
