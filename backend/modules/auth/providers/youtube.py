"""YouTube OAuth 2.0 — identity only; metrics use the Data API key adapter.

Scopes: youtube.readonly so we can read the creator's channel id and store
it on social_accounts for ownership checks on URL-only submissions.
"""

from urllib.parse import urlencode

import httpx

from core.config import get_settings

from .base import NormalizedToken, OAuthError, ProfileInfo

PLATFORM = "youtube"
USES_PKCE = False
SCOPES = "https://www.googleapis.com/auth/youtube.readonly"

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"


def authorize_url(state: str, code_verifier: str | None = None) -> str:
    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.youtube_client_id,
        "redirect_uri": settings.youtube_redirect_uri,
        "scope": SCOPES,
        "state": state,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, code_verifier: str | None = None) -> NormalizedToken:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.youtube_client_id,
                "client_secret": settings.youtube_client_secret,
                "redirect_uri": settings.youtube_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        payload = resp.json()
        if "access_token" not in payload:
            raise OAuthError(f"YouTube token exchange failed: {payload}")

        channel = await client.get(
            CHANNELS_URL,
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {payload['access_token']}"},
        )
        items = (channel.json() or {}).get("items") or []
        if not items:
            raise OAuthError("YouTube returned no channel for this account.")
        channel_id = str(items[0].get("id") or "")
        if not channel_id:
            raise OAuthError("YouTube channel response missing id.")

    return NormalizedToken(
        access_token=payload["access_token"],
        platform_user_id=channel_id,
        refresh_token=payload.get("refresh_token"),
        expires_in=payload.get("expires_in"),
    )


async def fetch_profile(access_token: str, platform_user_id: str) -> ProfileInfo | None:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            CHANNELS_URL,
            params={"part": "snippet", "id": platform_user_id},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    items = (resp.json() or {}).get("items") or []
    if not items:
        return None
    snippet = items[0].get("snippet") or {}
    title = snippet.get("title") or platform_user_id
    custom = snippet.get("customUrl")
    handle = custom if custom and custom.startswith("@") else (f"@{custom}" if custom else title)
    return ProfileInfo(handle=handle, display_name=title)
