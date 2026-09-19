"""Threads Login.

Requires an https redirect URI even in dev — tunnel with ngrok /
cloudflared and set THREADS_REDIRECT_URI to that public https URL.
"""

from urllib.parse import urlencode

import httpx

from core.config import get_settings

from .base import NormalizedToken, OAuthError

PLATFORM = "threads"
USES_PKCE = False
SCOPES = "threads_basic,threads_manage_insights,threads_read_replies"

AUTH_URL = "https://threads.net/oauth/authorize"
TOKEN_URL = "https://graph.threads.net/oauth/access_token"
LONG_LIVED_TOKEN_URL = "https://graph.threads.net/access_token"


def authorize_url(state: str, code_verifier: str | None = None) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.threads_app_id,
        "redirect_uri": settings.threads_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, code_verifier: str | None = None) -> NormalizedToken:
    settings = get_settings()

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.threads_app_id,
                "client_secret": settings.threads_app_secret,
                "grant_type": "authorization_code",
                "redirect_uri": settings.threads_redirect_uri,
                "code": code,
            },
        )
        payload = resp.json()
        if "access_token" not in payload:
            raise OAuthError(f"Threads token exchange failed: {payload}")
        short_token = payload["access_token"]
        user_id = str(payload.get("user_id", ""))

        ll_resp = await client.get(
            LONG_LIVED_TOKEN_URL,
            params={
                "grant_type": "th_exchange_token",
                "client_secret": settings.threads_app_secret,
                "access_token": short_token,
            },
        )
    ll_payload = ll_resp.json()
    if "access_token" in ll_payload:
        return NormalizedToken(
            access_token=ll_payload["access_token"],
            platform_user_id=user_id,
            expires_in=int(ll_payload.get("expires_in", 5_184_000)),
        )
    return NormalizedToken(access_token=short_token, platform_user_id=user_id, expires_in=3600)
