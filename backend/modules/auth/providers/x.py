"""X OAuth 2.0 PKCE. Identity only — metrics live in the twitterapi.io adapter.

Scopes: tweet.read, users.read, offline.access so we can store the user
id and a refresh_token.
"""

import base64
import hashlib
from urllib.parse import urlencode

import httpx

from core.config import get_settings

from .base import NormalizedToken, OAuthError, ProfileInfo

PLATFORM = "x"
USES_PKCE = True
SCOPES = "tweet.read users.read offline.access"

AUTH_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
ME_URL = "https://api.twitter.com/2/users/me"


def make_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def authorize_url(state: str, code_verifier: str) -> str:
    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.x_client_id,
        "redirect_uri": settings.x_redirect_uri,
        "scope": SCOPES,
        "state": state,
        "code_challenge": make_code_challenge(code_verifier),
        "code_challenge_method": "S256",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, code_verifier: str | None) -> NormalizedToken:
    settings = get_settings()
    basic = base64.b64encode(
        f"{settings.x_client_id}:{settings.x_client_secret}".encode()
    ).decode()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            TOKEN_URL,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {basic}",
            },
            data={
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.x_redirect_uri,
                "code_verifier": code_verifier or "",
            },
        )
        payload = resp.json()
        if "access_token" not in payload:
            raise OAuthError(f"X token exchange failed: {payload}")

        me = await client.get(
            ME_URL,
            headers={"Authorization": f"Bearer {payload['access_token']}"},
            params={"user.fields": "username"},
        )
        user = (me.json() or {}).get("data") or {}

    return NormalizedToken(
        access_token=payload["access_token"],
        platform_user_id=str(user.get("id") or user.get("username") or ""),
        refresh_token=payload.get("refresh_token"),
        expires_in=payload.get("expires_in"),
    )


async def fetch_profile(access_token: str, platform_user_id: str) -> ProfileInfo | None:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            ME_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params={"user.fields": "username,name"},
        )
    user = (resp.json() or {}).get("data") or {}
    username = user.get("username")
    if not username:
        return None
    return ProfileInfo(handle=f"@{username}", display_name=user.get("name") or username)
