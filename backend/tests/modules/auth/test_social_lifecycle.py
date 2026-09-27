"""Social token refresh, profile sync, and platform-initiated webhooks
(production-api-inventory.md §F). Meta signature verification is
exercised against `core.meta_webhooks`' own format — unverified against
real Meta traffic (see that module's docstring)."""

import base64
import hashlib
import hmac
import json

import pytest

from core.config import get_settings
from tests.http_app import api, auth, connect_account, signup


def _signed_request(payload: dict, secret: str) -> str:
    def b64url(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    encoded_payload = b64url(json.dumps(payload).encode())
    sig = hmac.new(secret.encode(), encoded_payload.encode(), hashlib.sha256).digest()
    return f"{b64url(sig)}.{encoded_payload}"


async def test_refresh_with_no_provider_support_reports_reconnect_required(api):
    _, creator = await signup(api, "creator")
    await connect_account(creator["user"]["id"], "facebook", "@creator")
    r = await api.post("/social/facebook/refresh", headers=auth(creator))
    assert r.status_code == 200 and r.json() == {
        "reconnect_required": True, "reason": "This platform has no automatic refresh; reconnect it.",
    }


async def test_refresh_without_a_connected_account_is_404(api):
    _, creator = await signup(api, "creator")
    r = await api.post("/social/tiktok/refresh", headers=auth(creator))
    assert r.status_code == 404


async def test_refresh_with_an_unknown_platform_is_404(api):
    _, creator = await signup(api, "creator")
    r = await api.post("/social/myspace/refresh", headers=auth(creator))
    assert r.status_code == 404


async def test_tiktok_refresh_calls_the_real_grant_and_updates_the_stored_token(api, monkeypatch):
    _, creator = await signup(api, "creator")
    await connect_account(creator["user"]["id"], "tiktok", "@creator")

    from modules.auth.providers import tiktok
    from modules.auth.providers.base import NormalizedToken

    async def fake_refresh(refresh_token: str) -> NormalizedToken:
        assert refresh_token == "refresh-dummy-token"
        return NormalizedToken(access_token="new-access", platform_user_id="uid-1", refresh_token="new-refresh", expires_in=3600)

    monkeypatch.setattr(tiktok, "refresh", fake_refresh)

    import uuid as _uuid

    from sqlalchemy import select

    from modules.auth.models import Platform, SocialAccount
    from tests.http_app import db_session

    async with db_session() as db:
        acc = await db.scalar(
            select(SocialAccount).where(
                SocialAccount.user_id == _uuid.UUID(creator["user"]["id"]), SocialAccount.platform == Platform.tiktok
            )
        )
        acc.refresh_token = "refresh-dummy-token"
        await db.commit()

    r = await api.post("/social/tiktok/refresh", headers=auth(creator))
    assert r.status_code == 200 and r.json()["reconnect_required"] is False


async def test_sync_profile_updates_handle_and_display_name(api, monkeypatch):
    _, creator = await signup(api, "creator")
    await connect_account(creator["user"]["id"], "tiktok", "@old_handle")

    from modules.auth.providers import tiktok
    from modules.auth.providers.base import ProfileInfo

    async def fake_fetch_profile(access_token, platform_user_id):
        return ProfileInfo(handle="@new_handle", display_name="New Name")

    monkeypatch.setattr(tiktok, "fetch_profile", fake_fetch_profile)

    r = await api.post("/social/tiktok/sync-profile", headers=auth(creator))
    assert r.status_code == 200
    body = r.json()
    assert body["handle"] == "@new_handle" and body["display_name"] == "New Name"


async def test_meta_deauthorize_webhook_disconnects_the_account(api, monkeypatch):
    from sqlalchemy import select

    settings = get_settings()
    secret = "test-fb-app-secret"
    monkeypatch.setattr(settings, "facebook_app_secret", secret)
    _, creator = await signup(api, "creator")
    await connect_account(creator["user"]["id"], "facebook", "@creator")

    accounts_before = (await api.get("/social/accounts", headers=auth(creator))).json()
    assert any(a["platform"] == "facebook" for a in accounts_before)

    from tests.http_app import db_session
    from modules.auth.models import SocialAccount
    async with db_session() as db:
        acc = await db.scalar(select(SocialAccount).where(SocialAccount.platform == "facebook"))

    signed = _signed_request({"algorithm": "HMAC-SHA256", "user_id": acc.platform_user_id}, secret)
    r = await api.post("/webhooks/social/facebook/deauthorize", data={"signed_request": signed})
    assert r.status_code == 200 and r.json() == {"received": True}

    accounts_after = (await api.get("/social/accounts", headers=auth(creator))).json()
    assert not any(a["platform"] == "facebook" for a in accounts_after)


async def test_meta_webhook_with_a_bad_signature_is_refused(api, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "facebook_app_secret", "real-secret")
    bad = _signed_request({"algorithm": "HMAC-SHA256", "user_id": "x"}, "wrong-secret")
    r = await api.post("/webhooks/social/facebook/deauthorize", data={"signed_request": bad})
    assert r.status_code == 401


async def test_meta_data_deletion_returns_a_status_url_and_confirmation_code(api, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "instagram_app_secret", "ig-secret")
    signed = _signed_request({"algorithm": "HMAC-SHA256", "user_id": "some-ig-id"}, "ig-secret")
    r = await api.post("/webhooks/social/instagram/data-deletion", data={"signed_request": signed})
    assert r.status_code == 200
    body = r.json()
    assert "url" in body and "confirmation_code" in body and len(body["confirmation_code"]) == 16


async def test_a_platform_with_no_signed_webhook_contract_is_404(api):
    r = await api.post("/webhooks/social/tiktok/deauthorize", data={"signed_request": "irrelevant"})
    assert r.status_code == 404


async def test_connecting_a_platform_without_oauth_credentials_bounces_back_to_settings(api, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "instagram_app_id", "")
    _, creator = await signup(api, "creator")
    r = await api.get("/social/instagram/login", headers=auth(creator))
    assert r.status_code == 307
    assert r.headers["location"] == f"{settings.app_url}/dashboard/settings?social=instagram&status=error&reason=not_configured"


async def test_connecting_a_configured_platform_sends_the_registered_redirect_uri(api, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "tiktok_client_key", "tk")
    monkeypatch.setattr(settings, "tiktok_client_secret", "ts")
    monkeypatch.setattr(settings, "tiktok_redirect_uri", "https://api.example.com/social/tiktok/callback")
    _, creator = await signup(api, "creator")
    r = await api.get("/social/tiktok/login", headers=auth(creator))
    assert r.status_code == 307
    location = r.headers["location"]
    assert location.startswith("https://www.tiktok.com/v2/auth/authorize/")
    assert "redirect_uri=https%3A%2F%2Fapi.example.com%2Fsocial%2Ftiktok%2Fcallback" in location


async def test_threads_is_not_connectable_in_v1_even_with_credentials(api, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "threads_app_id", "tid")
    monkeypatch.setattr(settings, "threads_app_secret", "tsecret")
    _, creator = await signup(api, "creator")
    r = await api.get("/social/threads/login", headers=auth(creator))
    assert r.status_code == 307 and "reason=not_configured" in r.headers["location"]
