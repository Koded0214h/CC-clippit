"""TikTok adapter — Display API v2.

Ported from the working prototype in `backend/service-test/tt/service.py`,
with three changes that matter:

- it fetches **one known video** (`/v2/video/query/`) instead of listing a
  creator's whole feed, because ingestion starts from a submitted URL;
- it returns the canonical dataclasses from `base.py` rather than raw JSON;
- it raises the typed errors, so the Stage 3 poller can decide what to do.

**Ownership is structural here.** TikTok's docs are explicit that
`/v2/video/query/` "verifies that the videos belong to the user" — it only
ever returns videos owned by whoever the access token belongs to. So a
video coming back at all *is* the ownership proof. There is no way to read
an arbitrary creator's TikTok video with Display API credentials, which is
also why `requires_creator_token` is True.

**No retries in here.** The adapter reports what happened (`RateLimited`
carries `retry_after` when TikTok tells us); the job layer owns backoff.
Retrying in both places would silently multiply every request — decision
D13 in `architecture/intelligence-contracts.md`.

Docs: https://developers.tiktok.com/doc/tiktok-api-v2-video-query
Rate limit: 600 requests/minute per endpoint, sliding window.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from core.platforms import Platform

from .base import (
    AdapterError,
    CapabilityNotSupported,
    CommentPage,
    ContentKind,
    ContentUnavailable,
    CreatorTokenExpired,
    PlatformContent,
    PlatformMetrics,
    PostType,
    RateLimited,
    UpstreamError,
)

VIDEO_QUERY_URL = "https://open.tiktokapis.com/v2/video/query/"

#: Everything we want per video. `is_aigc` is requested even though nothing
#: reads it yet — it's a free AI-generated-content flag that the Stage 5
#: trust rules will want, and it costs nothing to start capturing now.
VIDEO_FIELDS = ",".join(
    [
        "id",
        "title",
        "video_description",
        "duration",
        "cover_image_url",
        "share_url",
        "create_time",
        "view_count",
        "like_count",
        "comment_count",
        "share_count",
        "is_aigc",
    ]
)

#: TikTok's own hosts only. `resolve_url` refuses to make a request to
#: anything outside this set, so a creator can't get the backend to fetch
#: an arbitrary URL by pasting it into a submission.
CANONICAL_HOSTS = {"tiktok.com", "www.tiktok.com", "m.tiktok.com"}
SHORT_HOSTS = {"vm.tiktok.com", "vt.tiktok.com"}

VIDEO_ID_RE = re.compile(r"/video/(\d+)")
SHORT_PATH_RE = re.compile(r"^/(?:t/)?[A-Za-z0-9]+/?$")

#: Token problems the creator has to fix by reconnecting the account.
TOKEN_ERROR_CODES = {
    "access_token_invalid",
    "access_token_expired",
    "scope_not_authorized",
    "scope_permission_missed",
}


def _retry_after_seconds(headers: httpx.Headers) -> int | None:
    """TikTok may answer with `Retry-After` (seconds) or `X-RateLimit-Reset`
    (which is an absolute epoch second). Normalize both to "wait this long"."""
    raw = headers.get("Retry-After") or headers.get("X-RateLimit-Reset")
    if not raw:
        return None
    try:
        value = int(float(raw))
    except (TypeError, ValueError):
        return None
    if value > 10_000_000:  # too large to be a duration; it's a timestamp
        return max(0, value - int(time.time()))
    return max(0, value)


def _username_from_share_url(share_url: str | None) -> str | None:
    """TikTok share URLs are `https://www.tiktok.com/@handle/video/123`, so
    the handle is free — no second API call to `/v2/user/info/` just to
    label the author. Ownership is already guaranteed by the endpoint."""
    if not share_url:
        return None
    match = re.search(r"/@([^/?#]+)", share_url)
    return match.group(1) if match else None


class TikTokAdapter:
    """Implements `SocialPlatformAdapter` for TikTok.

    `transport` exists so tests can inject `httpx.MockTransport` and run
    against recorded payloads without credentials or network.
    """

    platform = Platform.tiktok
    requires_creator_token = True

    #: The Display API returns comment *counts* but never comment text, and
    #: there is no comments endpoint at all. Stage 6's comment intelligence
    #: simply cannot cover TikTok through this product.
    supports_comments = False

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

    # --- URL -> content id --------------------------------------------------
    async def resolve_url(self, url: str) -> str | None:
        """`https://www.tiktok.com/@handle/video/7123…` -> `"7123…"`.

        Short links (`vm.tiktok.com/ZM…`) carry no ID, so they need one
        redirect followed before the real URL is visible. Returns None for
        anything that isn't a TikTok URL — a normal answer, not an error,
        so a caller can try adapters in turn.
        """
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower()

        if host not in CANONICAL_HOSTS and host not in SHORT_HOSTS:
            return None

        match = VIDEO_ID_RE.search(parsed.path)
        if match:
            return match.group(1)

        is_short = host in SHORT_HOSTS or parsed.path.startswith("/t/")
        if not (is_short and SHORT_PATH_RE.match(parsed.path)):
            return None

        try:
            async with self._client() as client:
                resp = await client.get(url, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise UpstreamError(f"Could not follow TikTok short link {url}: {exc}") from exc

        final = VIDEO_ID_RE.search(urlparse(str(resp.url)).path)
        return final.group(1) if final else None

    # --- Reads --------------------------------------------------------------
    async def get_content(self, content_id: str, *, access_token: str | None = None) -> PlatformContent:
        video = await self._query_one(content_id, access_token)
        return self._to_content(video)

    async def get_metrics(self, content_id: str, *, access_token: str | None = None) -> PlatformMetrics:
        video = await self._query_one(content_id, access_token)
        return self._to_metrics(video)

    async def get_comments(
        self,
        content_id: str,
        *,
        access_token: str | None = None,
        cursor: str | None = None,
    ) -> CommentPage:
        raise CapabilityNotSupported(
            "TikTok's Display API exposes comment counts but not comment text."
        )

    async def query_videos(self, content_ids: list[str], access_token: str) -> list[dict[str, Any]]:
        """Raw fetch for up to 20 videos in one call.

        Public because Stage 3 should batch: polling 20 submissions costs
        one request here instead of twenty. `get_metrics` is the single-item
        convenience on top of it.
        """
        if not content_ids:
            return []
        if len(content_ids) > 20:
            raise AdapterError(f"TikTok allows at most 20 video ids per query, got {len(content_ids)}.")
        if not access_token:
            raise AdapterError("TikTok requires the creator's access token; none was supplied.")

        try:
            async with self._client() as client:
                resp = await client.post(
                    VIDEO_QUERY_URL,
                    params={"fields": VIDEO_FIELDS},
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json={"filters": {"video_ids": content_ids}},
                )
        except httpx.HTTPError as exc:
            raise UpstreamError(f"TikTok request failed: {exc}") from exc

        self._raise_for_status(resp)
        payload = self._parse_json(resp)
        self._raise_for_api_error(payload)
        return (payload.get("data") or {}).get("videos") or []

    # --- Internals ----------------------------------------------------------
    async def _query_one(self, content_id: str, access_token: str | None) -> dict[str, Any]:
        videos = await self.query_videos([content_id], access_token or "")
        if not videos:
            # TikTok answers "ok" with an empty list for a video that is
            # deleted, private, *or* simply owned by someone else — it never
            # distinguishes them. `ContentUnavailable` is the honest answer;
            # claiming `ContentNotFound` would assert more than we know.
            raise ContentUnavailable(
                f"TikTok returned no video for id {content_id}: it is deleted, private, "
                "or does not belong to the connected creator."
            )
        return videos[0]

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code == 429:
            raise RateLimited(
                "TikTok rate limit hit (600 requests/minute per endpoint).",
                retry_after=_retry_after_seconds(resp.headers),
            )
        if resp.status_code in (401, 403):
            raise CreatorTokenExpired(
                f"TikTok rejected the creator's access token (HTTP {resp.status_code})."
            )
        if resp.status_code >= 500:
            raise UpstreamError(f"TikTok returned HTTP {resp.status_code}.")

    @staticmethod
    def _parse_json(resp: httpx.Response) -> dict[str, Any]:
        try:
            return resp.json()
        except ValueError as exc:
            raise UpstreamError(f"TikTok returned a non-JSON body (HTTP {resp.status_code}).") from exc

    @staticmethod
    def _raise_for_api_error(payload: dict[str, Any]) -> None:
        """TikTok answers HTTP 200 with an `error.code` of `"ok"` on success,
        so the status line alone never proves anything worked."""
        error = payload.get("error") or {}
        code = error.get("code")
        if code in (None, "ok"):
            return

        message = error.get("message") or "no message"
        log_id = error.get("log_id")
        detail = f"TikTok error '{code}': {message}" + (f" (log_id {log_id})" if log_id else "")

        if code in TOKEN_ERROR_CODES:
            raise CreatorTokenExpired(detail)
        if code == "rate_limit_exceeded":
            raise RateLimited(detail)
        if code == "invalid_params":
            # Our bug, not theirs — a malformed field list or video id.
            raise AdapterError(detail)
        raise UpstreamError(detail)

    # --- Normalization ------------------------------------------------------
    @staticmethod
    def _to_content(video: dict[str, Any]) -> PlatformContent:
        share_url = video.get("share_url") or ""
        created = video.get("create_time")
        return PlatformContent(
            platform=Platform.tiktok,
            platform_content_id=str(video.get("id", "")),
            url=share_url,
            author_platform_user_id=None,  # implied by the token; see module docstring
            author_username=_username_from_share_url(share_url),
            kind=ContentKind.video,
            # The Display API exposes no repost/duet/stitch marker, so every
            # video reads as original. Revisit if TikTok ever surfaces it.
            post_type=PostType.original,
            caption=video.get("video_description") or video.get("title"),
            published_at=(
                datetime.fromtimestamp(created, tz=timezone.utc) if isinstance(created, int) else None
            ),
            raw=video,
        )

    @staticmethod
    def _to_metrics(video: dict[str, Any]) -> PlatformMetrics:
        return PlatformMetrics(
            platform=Platform.tiktok,
            platform_content_id=str(video.get("id", "")),
            observed_at=datetime.now(timezone.utc),
            views=video.get("view_count"),
            likes=video.get("like_count"),
            comments=video.get("comment_count"),
            shares=video.get("share_count"),
            # TikTok's Display API reports none of these. They stay None so
            # nothing downstream mistakes "not reported" for "zero".
            saves=None,
            reach=None,
            impressions=None,
            raw=video,
        )
