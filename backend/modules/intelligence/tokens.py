"""How this module gets a creator's platform access token.

Tokens live in `social_accounts`, which belongs to Auth & Accounts. We do
**not** import that model or query that table — the documented way in is
`GET /internal/social-accounts/{user_id}/{platform}/token`, guarded by the
shared internal secret, and that's what `InternalApiTokenSource` calls.

Yes, inside one monolith this is a loopback HTTP request where a function
call would do. That's a deliberate trade: the boundary stays real, the
call keeps working unchanged if these modules are ever split, and — the
part that actually matters day to day — swapping in an in-process
implementation later means writing one new class that satisfies
`TokenSource`, with nothing in `ingestion.py` touched. Decision D14.

`StaticTokenSource` is the same port backed by a dict, for tests and for
poking at a real platform from a script without running the whole app.
"""

from __future__ import annotations

import uuid
from typing import Protocol

import httpx

from core.config import get_settings
from core.platforms import Platform

from .errors import MissingCreatorToken, TokenLookupFailed

DEFAULT_INTERNAL_BASE_URL = "http://127.0.0.1:8000"


class TokenSource(Protocol):
    async def token_for(self, creator_id: uuid.UUID, platform: Platform) -> str:
        """Return a usable access token, or raise `MissingCreatorToken`."""
        ...


class InternalApiTokenSource:
    """Reads tokens through the auth module's internal endpoint.

    `base_url` is a constructor argument rather than a setting on purpose:
    nothing in `core/config.py` needs to change for Stage 2, and whoever
    wires the poller in Stage 3 decides where the internal API lives.
    """

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_INTERNAL_BASE_URL,
        secret: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._secret = secret if secret is not None else get_settings().internal_service_secret
        self._transport = transport
        self._timeout = timeout

    async def token_for(self, creator_id: uuid.UUID, platform: Platform) -> str:
        url = f"{self._base_url}/internal/social-accounts/{creator_id}/{platform.value}/token"
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                resp = await client.get(url, headers={"X-Internal-Secret": self._secret})
        except httpx.HTTPError as exc:
            raise TokenLookupFailed(f"Could not reach the auth module: {exc}") from exc

        if resp.status_code == 404:
            raise MissingCreatorToken(
                f"Creator {creator_id} has no connected {platform.value} account."
            )
        if resp.status_code == 409:
            # Auth returns 409 for an expired token it can't refresh.
            raise MissingCreatorToken(
                f"Creator {creator_id}'s {platform.value} token has expired; they must reconnect."
            )
        if resp.status_code == 401:
            raise TokenLookupFailed(
                "The auth module rejected our internal secret — check INTERNAL_SERVICE_SECRET."
            )
        if resp.status_code == 422:
            # Auth's DB enum doesn't know this platform yet. Exactly the
            # gap decision D5 tracks; it'll bite when X or YouTube lands.
            raise TokenLookupFailed(
                f"The auth module doesn't recognise platform '{platform.value}' (see decision D5)."
            )
        if resp.status_code != 200:
            raise TokenLookupFailed(
                f"Unexpected {resp.status_code} from the auth module's token endpoint."
            )

        try:
            token = (resp.json() or {}).get("access_token")
        except ValueError as exc:
            raise TokenLookupFailed("The auth module returned a non-JSON token response.") from exc

        if not token:
            raise MissingCreatorToken(
                f"Auth returned an empty {platform.value} token for creator {creator_id}."
            )
        return token


class StaticTokenSource:
    """A dict pretending to be the auth module."""

    def __init__(self, tokens: dict[tuple[uuid.UUID, Platform], str] | None = None) -> None:
        self._tokens = tokens or {}

    def set(self, creator_id: uuid.UUID, platform: Platform, token: str) -> None:
        self._tokens[(creator_id, platform)] = token

    async def token_for(self, creator_id: uuid.UUID, platform: Platform) -> str:
        token = self._tokens.get((creator_id, platform))
        if not token:
            raise MissingCreatorToken(
                f"No token configured for creator {creator_id} on {platform.value}."
            )
        return token
