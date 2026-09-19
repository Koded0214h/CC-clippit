"""X adapter — identity is OAuth; metrics and replies come from twitterapi.io.

The official X API is too expensive for read-heavy polling (decision D8).
Creators still connect via OAuth so we know *who* submitted; this adapter
talks to twitterapi.io with `TWITTERAPI_IO_KEY`. Trial keys rate-limit
aggressively after a few reads.

Only `original` and `quote` posts are campaign-submittable. Reposts and
replies are classified so ingestion can reject them.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from core.config import get_settings
from core.platforms import Platform

from .base import (
    AdapterError,
    CommentPage,
    ContentKind,
    ContentUnavailable,
    CreatorTokenExpired,
    PlatformComment,
    PlatformContent,
    PlatformMetrics,
    PostType,
    RateLimited,
    UpstreamError,
)

IO_BASE = "https://api.twitterapi.io"
TWEET_ID_RE = re.compile(r"(?:twitter\.com|x\.com)/[^/]+/status/(\d+)", re.I)
HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}


class XAdapter:
    platform = Platform.x
    source = "twitterapi.io"
    #: Metrics don't need the creator's X token — they use TWITTERAPI_IO_KEY.
    #: Submissions still require a connected X account at the Core layer.
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
        key = self._api_key if self._api_key is not None else get_settings().twitterapi_io_key
        if not key:
            raise AdapterError("TWITTERAPI_IO_KEY is not configured.")
        return key

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
            headers={"x-api-key": self._key()},
        )

    async def resolve_url(self, url: str) -> str | None:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower()
        if host not in HOSTS:
            return None
        match = TWEET_ID_RE.search(url)
        return match.group(1) if match else None

    async def get_content(self, content_id: str, *, access_token: str | None = None) -> PlatformContent:
        tweet = await self._tweet(content_id)
        return self._to_content(tweet)

    async def get_metrics(self, content_id: str, *, access_token: str | None = None) -> PlatformMetrics:
        tweet = await self._tweet(content_id)
        return self._to_metrics(tweet)

    async def get_comments(
        self,
        content_id: str,
        *,
        access_token: str | None = None,
        cursor: str | None = None,
    ) -> CommentPage:
        params: dict[str, Any] = {"tweetId": content_id}
        if cursor:
            params["cursor"] = cursor
        payload = await self._io_get("/twitter/tweet/replies", params)
        raw = _extract_tweets(payload)
        comments = [
            PlatformComment(
                platform=Platform.x,
                platform_comment_id=str(row.get("id", "")),
                platform_content_id=content_id,
                text=row.get("text") or "",
                author_platform_user_id=str((row.get("author") or {}).get("id") or "") or None,
                author_username=(row.get("author") or {}).get("userName")
                or (row.get("author") or {}).get("username"),
                likes=row.get("likeCount") or row.get("like_count"),
                created_at=_parse_created(row),
                raw=row,
            )
            for row in raw
        ]
        next_cursor = payload.get("next_cursor") or None
        has_more = bool(payload.get("has_next_page") and next_cursor)
        return CommentPage(comments=comments, next_cursor=next_cursor, has_more=has_more)

    async def _tweet(self, tweet_id: str) -> dict[str, Any]:
        payload = await self._io_get("/twitter/tweets", {"tweet_ids": tweet_id})
        tweets = _extract_tweets(payload)
        if not tweets:
            raise ContentUnavailable(f"X returned no tweet for id {tweet_id}.")
        return tweets[0]

    async def _io_get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            async with self._client() as client:
                resp = await client.get(f"{IO_BASE}{path}", params=params)
        except httpx.HTTPError as exc:
            raise UpstreamError(f"twitterapi.io request failed: {exc}") from exc

        if resp.status_code == 429:
            retry = resp.headers.get("Retry-After")
            raise RateLimited(
                "twitterapi.io rate limit hit.",
                retry_after=int(retry) if retry and str(retry).isdigit() else None,
            )
        if resp.status_code in (401, 403):
            raise CreatorTokenExpired(f"twitterapi.io rejected the API key (HTTP {resp.status_code}).")
        if resp.status_code >= 500:
            raise UpstreamError(f"twitterapi.io returned HTTP {resp.status_code}.")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise UpstreamError("twitterapi.io returned a non-JSON body.") from exc
        if payload.get("status") == "error":
            raise UpstreamError(payload.get("message") or payload.get("msg") or "twitterapi.io error")
        return payload

    @staticmethod
    def _to_content(tweet: dict[str, Any]) -> PlatformContent:
        author = tweet.get("author") or {}
        username = author.get("userName") or author.get("username")
        tweet_id = str(tweet.get("id", ""))
        return PlatformContent(
            platform=Platform.x,
            platform_content_id=tweet_id,
            url=tweet.get("url") or (f"https://x.com/{username}/status/{tweet_id}" if username else ""),
            author_platform_user_id=str(author.get("id")) if author.get("id") else None,
            author_username=username,
            kind=ContentKind.text,
            post_type=_classify(tweet),
            caption=tweet.get("text"),
            published_at=_parse_created(tweet),
            raw=tweet,
        )

    @staticmethod
    def _to_metrics(tweet: dict[str, Any]) -> PlatformMetrics:
        return PlatformMetrics(
            platform=Platform.x,
            platform_content_id=str(tweet.get("id", "")),
            observed_at=datetime.now(timezone.utc),
            views=tweet.get("viewCount") or tweet.get("view_count"),
            likes=tweet.get("likeCount") or tweet.get("like_count"),
            comments=tweet.get("replyCount") or tweet.get("reply_count"),
            shares=tweet.get("retweetCount") or tweet.get("retweet_count"),
            saves=None,
            reach=None,
            impressions=None,
            raw=tweet,
        )


def _extract_tweets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    tweets = payload.get("tweets")
    if tweets:
        return tweets
    inner = payload.get("data")
    if isinstance(inner, dict):
        return inner.get("tweets") or inner.get("replies") or []
    if isinstance(inner, list):
        return inner
    return payload.get("replies") or []


def _classify(raw: dict[str, Any]) -> PostType:
    if raw.get("retweeted_tweet"):
        return PostType.repost
    if raw.get("quoted_tweet"):
        return PostType.quote
    if raw.get("isReply"):
        return PostType.reply
    return PostType.original


def _parse_created(raw: dict[str, Any]) -> datetime | None:
    value = raw.get("createdAt") or raw.get("created_at")
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
