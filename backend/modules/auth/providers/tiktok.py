"""TikTok Login Kit (OAuth 2.0 + PKCE).

Ported from the working prototype in backend/service-test/tt/service.py —
same endpoints, same PKCE handshake. Requires user.info.basic + video.list
scopes for the Intelligence Engine to later read view/like counts.
"""

import base64
import hashlib
from urllib.parse import urlencode

import requests

from core.config import get_settings
from .base import NormalizedToken, OAuthError

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


def exchange_code(code: str, code_verifier: str | None) -> NormalizedToken:
    settings = get_settings()
    resp = requests.post(
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
        timeout=15,
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
