"""TikTok Login Kit (OAuth 2.0 + PKCE).

Requires user.info.basic + video.list so Intelligence can later read
view and like counts on the connected account's videos.
"""

import base64
import hashlib
from urllib.parse import urlencode

import httpx

from core.config import get_settings

from .base import NormalizedToken, OAuthError, ProfileInfo

PLATFORM = "tiktok"
USES_PKCE = True
SCOPES = "user.info.basic,video.list"

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


def make_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def authorize_url(state: str, code_verifier: str) -> str:
    settings = get_settings()
    params = {
        "client_key": settings.tiktok_client_key,
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": settings.tiktok_redirect_uri,
        "state": state,
        "code_challenge": make_code_challenge(code_verifier),
        "code_challenge_method": "S256",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, code_verifier: str | None) -> NormalizedToken:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": settings.tiktok_client_key,
                "client_secret": settings.tiktok_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.tiktok_redirect_uri,
                "code_verifier": code_verifier or "",
            },
        )
    payload = resp.json()
    if "access_token" not in payload:
        raise OAuthError(f"TikTok token exchange failed: {payload}")
    return NormalizedToken(
        access_token=payload["access_token"],
        platform_user_id=payload.get("open_id", ""),
        refresh_token=payload.get("refresh_token"),
        expires_in=payload.get("expires_in"),
    )


PROFILE_URL = "https://open.tiktokapis.com/v2/user/info/"


async def fetch_profile(access_token: str, platform_user_id: str) -> ProfileInfo | None:
    """`username` needs the user.info.profile scope we don't request, so the
    display name (user.info.basic) is what we can show."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            PROFILE_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params={"fields": "open_id,display_name,username"},
        )
    user = ((resp.json() or {}).get("data") or {}).get("user") or {}
    name = user.get("display_name")
    username = user.get("username")
    if not (name or username):
        return None
    return ProfileInfo(handle=f"@{username}" if username else name, display_name=name)
