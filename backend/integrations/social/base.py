"""The contract every social platform adapter implements.

An adapter's job is narrow on purpose: take a platform's API, hand back
Clippit-shaped data, and raise a Clippit-shaped error when it can't. It
translates; it does not decide. Nothing in here knows what a campaign is,
what a payout is, or whether a number looks suspicious — those live in
`modules/intelligence/` and above.

Three rules hold for every adapter:

1. **Raw is never thrown away.** Each returned object carries the provider
   response it was built from, so an integration bug can be diagnosed and
   old observations can be re-normalized later without re-fetching.
2. **Missing is not zero.** A metric the platform doesn't expose is `None`.
   Writing 0 would silently look like "nobody watched this".
3. **Failures are typed.** Callers (the polling jobs, mostly) branch on the
   exception class to decide retry vs. give up vs. ask the creator to
   reconnect. A bare `RuntimeError` forces them to parse strings.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from core.platforms import Platform


class ContentKind(str, enum.Enum):
    """What the submitted thing actually is. Campaign rules can require a
    video; a text post with a link is not the same deliverable."""

    video = "video"
    image = "image"
    text = "text"
    unknown = "unknown"


class PostType(str, enum.Enum):
    """Whether the creator made this, or merely passed it along.

    Learned the hard way while validating X: a creator's timeline is mostly
    reposts of other people's work. Only `original` and `quote` represent
    content the creator produced, so only those can be submitted against a
    campaign. See `backend/service-test/X/service.py`.
    """

    original = "original"
    quote = "quote"
    repost = "repost"
    reply = "reply"


@dataclass(frozen=True)
class PlatformContent:
    """A single piece of content as the platform describes it."""

    platform: Platform
    platform_content_id: str
    url: str
    author_platform_user_id: str | None = None
    author_username: str | None = None
    kind: ContentKind = ContentKind.unknown
    post_type: PostType = PostType.original
    caption: str | None = None
    published_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlatformMetrics:
    """One observation of a piece of content's counters.

    These are *cumulative totals as of `observed_at`*, not deltas. Turning
    a series of these into "views earned since yesterday" is the feature
    layer's job (Stage 4), because only it knows what the previous
    observation was.
    """

    platform: Platform
    platform_content_id: str
    observed_at: datetime
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None
    reach: int | None = None
    impressions: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlatformComment:
    """One comment/reply, for the trust and brand-intelligence pipelines."""

    platform: Platform
    platform_comment_id: str
    platform_content_id: str
    text: str
    author_platform_user_id: str | None = None
    author_username: str | None = None
    likes: int | None = None
    replies: int | None = None
    created_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CommentPage:
    """Comments come back paginated everywhere, with an opaque cursor."""

    comments: list[PlatformComment]
    next_cursor: str | None = None
    has_more: bool = False


# --- Failures ---------------------------------------------------------------
class AdapterError(RuntimeError):
    """Base class — catching this catches every adapter failure."""


class ContentNotFound(AdapterError):
    """The URL/ID doesn't resolve to anything on the platform."""


class ContentUnavailable(AdapterError):
    """It exists but we can't see it: private, deleted, geo-blocked, or
    owned by an account that isn't the connected creator. Distinct from
    `ContentNotFound` because the submission may become valid again."""


class CreatorTokenExpired(AdapterError):
    """The creator's OAuth token is dead. Not retryable by us — the creator
    has to reconnect the account, so this should surface to the product."""


class CapabilityNotSupported(AdapterError):
    """This platform can't answer this question at all (e.g. comment text
    on TikTok). Never retry; record it and move on."""


class RateLimited(AdapterError):
    """Back off and try again. `retry_after` is seconds when the provider
    tells us, otherwise None and the caller picks its own backoff."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class UpstreamError(AdapterError):
    """The platform failed in a way that is probably transient (5xx,
    timeout, malformed body). Retryable with backoff."""


# --- The interface ----------------------------------------------------------
@runtime_checkable
class SocialPlatformAdapter(Protocol):
    """Structural interface — an adapter is anything with these members.

    Declared as a `Protocol` rather than a base class so adapters stay
    independently testable and don't inherit behaviour they didn't ask
    for. Type checkers verify conformance; nothing has to subclass.

    The capability flags exist because platforms genuinely differ, and the
    plan is explicit that we should not paper over that. The pipeline reads
    the flags instead of calling a method and catching an exception.
    """

    platform: Platform

    #: True when reading metrics needs the creator's own OAuth token (TikTok,
    #: Instagram, Threads). False when any public URL can be read with a
    #: service-level key (X via twitterapi.io, YouTube Data API).
    requires_creator_token: bool

    #: True when the platform exposes comment *text*, not just a count.
    supports_comments: bool

    async def resolve_url(self, url: str) -> str | None:
        """Turn a creator-submitted URL into a platform content ID.

        Returns None when the URL clearly isn't for this platform. May do
        network I/O — short links (vm.tiktok.com, youtu.be) need a redirect
        followed before the ID is visible.
        """
        ...

    async def get_content(self, content_id: str, *, access_token: str | None = None) -> PlatformContent:
        """Identity and authorship of the content — who posted it, when,
        what kind of post it is. This is what ownership checks run against."""
        ...

    async def get_metrics(self, content_id: str, *, access_token: str | None = None) -> PlatformMetrics:
        """One metric observation, right now."""
        ...

    async def get_comments(
        self,
        content_id: str,
        *,
        access_token: str | None = None,
        cursor: str | None = None,
    ) -> CommentPage:
        """One page of comments. Adapters where `supports_comments` is
        False raise `CapabilityNotSupported`."""
        ...
