"""Instagram Business Login. Ported from backend/service-test/meta_insta/service.py."""

from urllib.parse import urlencode

import requests

from core.config import get_settings
from .base import NormalizedToken, OAuthError

PLATFORM = "instagram"
USES_PKCE = False
SCOPES = "instagram_business_basic,instagram_business_manage_insights"

AUTH_URL = "https://api.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
LONG_LIVED_TOKEN_URL = "https://graph.instagram.com/access_token"


def authorize_url(state: str, code_verifier: str | None = None) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.instagram_app_id,
        "redirect_uri": settings.instagram_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str, code_verifier: str | None = None) -> NormalizedToken:
    settings = get_settings()

    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": settings.instagram_app_id,
            "client_secret": settings.instagram_app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": settings.instagram_redirect_uri,
            "code": code,
        },
        timeout=15,
    )
    payload = resp.json()
    if "access_token" not in payload:
        raise OAuthError(f"Instagram token exchange failed: {payload}")
    short_token = payload["access_token"]
    user_id = str(payload.get("user_id", ""))

    ll_resp = requests.get(
        LONG_LIVED_TOKEN_URL,
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": settings.instagram_app_secret,
            "access_token": short_token,
        },
        timeout=15,
    )
    ll_payload = ll_resp.json()
    if "access_token" in ll_payload:
        return NormalizedToken(
            access_token=ll_payload["access_token"],
            platform_user_id=user_id,
            expires_in=int(ll_payload.get("expires_in", 5_184_000)),
        )
    return NormalizedToken(access_token=short_token, platform_user_id=user_id, expires_in=3600)
