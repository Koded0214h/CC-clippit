"""Google Sign-In (OIDC) — an identity provider for `/auth/*` itself, not
a connected social account (that's `modules.auth.social_router` /
`modules.auth.providers`, a completely different thing: a brand's TikTok
handle vs. "prove you're tobi@gmail.com").

Verifies the id_token via Google's `tokeninfo` endpoint rather than local
JWKS/RS256 verification — this environment doesn't have the `cryptography`
package installed (no prebuilt wheel here; a source build is slow enough
that earlier work pinned around it — see backend/README's test-setup
notes), and `tokeninfo` is Google's own documented alternative for exactly
that case. It's rate-limited for high volume; swap in local JWKS
verification (`jwt.PyJWKClient` needs `cryptography` for RS256) once that
constraint is gone.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from core.config import get_settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


class GoogleAuthError(RuntimeError):
    pass


def authorize_url(state: str, nonce: str) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


@dataclass
class GoogleIdentity:
    google_id: str
    email: str
    email_verified: bool
    name: str | None


async def exchange_code(code: str) -> str:
    """Returns the id_token — the only piece of the token response this
    flow needs, since sign-in doesn't call the Google API again later."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    payload = resp.json()
    if "id_token" not in payload:
        raise GoogleAuthError(f"Google token exchange failed: {payload}")
    return payload["id_token"]


async def verify_id_token(id_token: str, *, expected_nonce: str) -> GoogleIdentity:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(TOKENINFO_URL, params={"id_token": id_token})
    if resp.status_code != 200:
        raise GoogleAuthError("Google rejected this sign-in (expired or invalid token).")
    claims = resp.json()

    if claims.get("aud") != settings.google_client_id:
        raise GoogleAuthError("This sign-in wasn't issued for Clippit.")
    if claims.get("iss") not in ISSUERS:
        raise GoogleAuthError("Unexpected token issuer.")
    if claims.get("nonce") != expected_nonce:
        raise GoogleAuthError("This sign-in attempt doesn't match — start again.")
    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise GoogleAuthError("Google didn't return an account to sign in with.")

    return GoogleIdentity(
        google_id=sub,
        email=email,
        email_verified=str(claims.get("email_verified")).lower() == "true",
        name=claims.get("name"),
    )
