"""Facebook Login.

Only the account-connection handshake lives here (short-lived → long-lived
user token + the user's Facebook id). Reading Page posts is the Facebook
adapter's job, not part of connecting the account.
"""

from urllib.parse import urlencode

import httpx

from core.config import get_settings

from .base import NormalizedToken, OAuthError, ProfileInfo

PLATFORM = "facebook"
USES_PKCE = False
SCOPES = "pages_show_list,pages_read_engagement,pages_read_user_content"

GRAPH_VERSION = "v22.0"
AUTH_URL = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
TOKEN_URL = f"https://graph.facebook.com/{GRAPH_VERSION}/oauth/access_token"
GRAPH_API = f"https://graph.facebook.com/{GRAPH_VERSION}"


def authorize_url(state: str, code_verifier: str | None = None) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.facebook_app_id,
        "redirect_uri": settings.facebook_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, code_verifier: str | None = None) -> NormalizedToken:
    settings = get_settings()

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            TOKEN_URL,
            params={
                "client_id": settings.facebook_app_id,
                "client_secret": settings.facebook_app_secret,
                "redirect_uri": settings.facebook_redirect_uri,
                "code": code,
            },
        )
        payload = resp.json()
        if "access_token" not in payload:
            raise OAuthError(f"Facebook token exchange failed: {payload}")
        short_token = payload["access_token"]

        ll_resp = await client.get(
            TOKEN_URL,
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.facebook_app_id,
                "client_secret": settings.facebook_app_secret,
                "fb_exchange_token": short_token,
            },
        )
        ll_payload = ll_resp.json()
        user_token = ll_payload.get("access_token", short_token)
        expires_in = int(ll_payload.get("expires_in", 5_184_000))

        me_resp = await client.get(f"{GRAPH_API}/me", params={"access_token": user_token})
        user_id = me_resp.json().get("id", "")

    return NormalizedToken(access_token=user_token, platform_user_id=user_id, expires_in=expires_in)


async def fetch_profile(access_token: str, platform_user_id: str) -> ProfileInfo | None:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{GRAPH_API}/me", params={"fields": "id,name", "access_token": access_token})
    name = (resp.json() or {}).get("name")
    return ProfileInfo(handle=name, display_name=name) if name else None
