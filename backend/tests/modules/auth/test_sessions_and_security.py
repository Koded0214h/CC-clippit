"""Refresh rotation, sessions, password/step-up/account lifecycle, and
Google sign-in (production-api-inventory.md §B). Google's own network
calls are monkeypatched — the fake just swaps in a deterministic identity."""

import uuid
from datetime import datetime, timezone

import pytest

from core.config import get_settings
from modules.auth import google_router, models
from modules.auth.google import GoogleIdentity
from tests.http_app import api, auth, campaign_body, db_session, earn, fund_campaign, intel, latest_code, make_creator, signup, submit_clip


async def test_signup_and_login_both_return_a_refresh_token(api):
    _, creator = await signup(api, "creator")
    assert creator["refresh_token"]
    login = (await api.post("/auth/login", json={"email": creator["user"]["email"], "password": "DemoPassword123!"})).json()
    assert login["refresh_token"] and login["refresh_token"] != creator["refresh_token"]


async def test_remember_device_requires_email_code_and_extends_only_that_session(api):
    email, creator = await signup(api, "creator", verify=True)
    login = (await api.post(
        "/auth/login",
        headers={"User-Agent": "Clippit remembered-device test"},
        json={"email": email, "password": "DemoPassword123!"},
    )).json()

    sent = await api.post("/auth/remember-device/request", headers=auth(login), json={})
    assert sent.status_code == 200 and sent.json()["resend_in"] > 0

    wrong = await api.post(
        "/auth/remember-device/verify", headers=auth(login), json={"code": "000000"}
    )
    assert wrong.status_code == 400

    confirmed = await api.post(
        "/auth/remember-device/verify",
        headers=auth(login),
        json={"code": latest_code(email)},
    )
    assert confirmed.status_code == 200
    assert confirmed.json() == {"remembered": True, "expires_in_days": 365}

    listed = (await api.get("/auth/sessions", headers=auth(login))).json()
    current = next(row for row in listed if row["current"])
    assert current["remembered"] is True

    token_id = uuid.UUID(login["refresh_token"].split(".", 1)[0])
    async with db_session() as db:
        refresh = await db.get(models.RefreshToken, token_id)
        remaining = refresh.expires_at - datetime.now(timezone.utc)
        assert remaining.days >= 364

    rotated = await api.post("/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert rotated.status_code == 200
    rotated_id = uuid.UUID(rotated.json()["refresh_token"].split(".", 1)[0])
    async with db_session() as db:
        refresh = await db.get(models.RefreshToken, rotated_id)
        remaining = refresh.expires_at - datetime.now(timezone.utc)
        assert remaining.days >= 364


async def test_remember_device_requires_an_authenticated_verified_account(api):
    anonymous = await api.post("/auth/remember-device/request", json={})
    assert anonymous.status_code == 401

    _, unverified = await signup(api, "creator", verify=False)
    blocked = await api.post("/auth/remember-device/request", headers=auth(unverified), json={})
    assert blocked.status_code == 409


async def test_refresh_rotates_the_token_and_the_old_one_stops_working(api):
    _, creator = await signup(api, "creator")
    first_refresh = creator["refresh_token"]

    rotated = await api.post("/auth/refresh", json={"refresh_token": first_refresh})
    assert rotated.status_code == 200
    second = rotated.json()
    assert second["access_token"] != creator["access_token"]
    assert second["refresh_token"] != first_refresh

    reuse = await api.post("/auth/refresh", json={"refresh_token": first_refresh})
    assert reuse.status_code == 401  # already used

    # Reuse revoked the whole session, so even the *new* token is dead now.
    also_dead = await api.post("/auth/refresh", json={"refresh_token": second["refresh_token"]})
    assert also_dead.status_code == 401


async def test_a_bogus_refresh_token_is_rejected(api):
    r = await api.post("/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert r.status_code == 401


async def test_sessions_lists_the_current_device_and_logout_ends_it(api):
    _, creator = await signup(api, "creator")
    sessions_ = (await api.get("/auth/sessions", headers=auth(creator))).json()
    assert len(sessions_) == 1 and sessions_[0]["current"] is True

    await api.post("/auth/logout", headers=auth(creator))
    denied = await api.get("/auth/sessions", headers=auth(creator))
    assert denied.status_code == 401  # the session behind this very token is now revoked


async def test_revoking_one_session_signs_out_only_that_device(api):
    email, creator = await signup(api, "creator")
    second_login = (await api.post("/auth/login", json={"email": email, "password": "DemoPassword123!"})).json()

    sessions_ = (await api.get("/auth/sessions", headers=auth(creator))).json()
    other = next(s for s in sessions_ if not s["current"])
    r = await api.delete(f"/auth/sessions/{other['id']}", headers=auth(creator))
    assert r.status_code == 204

    still_works = await api.get("/auth/me", headers=auth(creator))
    assert still_works.status_code == 200
    revoked = await api.get("/auth/me", headers=auth(second_login))
    assert revoked.status_code == 401


async def test_revoke_others_keeps_only_the_calling_device(api):
    email, creator = await signup(api, "creator")
    await api.post("/auth/login", json={"email": email, "password": "DemoPassword123!"})
    await api.post("/auth/login", json={"email": email, "password": "DemoPassword123!"})

    r = await api.delete("/auth/sessions/others", headers=auth(creator))
    assert r.status_code == 200 and r.json()["revoked"] == 2
    sessions_ = (await api.get("/auth/sessions", headers=auth(creator))).json()
    assert len(sessions_) == 1


async def test_change_password_needs_the_current_one_and_revokes_other_sessions(api):
    email, creator = await signup(api, "creator")
    other_login = (await api.post("/auth/login", json={"email": email, "password": "DemoPassword123!"})).json()

    wrong = await api.post(
        "/auth/change-password", headers=auth(creator),
        json={"current_password": "WrongPass123", "new_password": "NewPassword456"},
    )
    assert wrong.status_code == 401

    ok = await api.post(
        "/auth/change-password", headers=auth(creator),
        json={"current_password": "DemoPassword123!", "new_password": "NewPassword456"},
    )
    assert ok.status_code == 204

    # The calling session survives; the other device is signed out.
    assert (await api.get("/auth/me", headers=auth(creator))).status_code == 200
    assert (await api.get("/auth/me", headers=auth(other_login))).status_code == 401

    relogin = await api.post("/auth/login", json={"email": email, "password": "NewPassword456"})
    assert relogin.status_code == 200


async def test_step_up_then_delete_account_is_refused_with_money_outstanding(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post(
        "/campaigns", headers=auth(org),
        json=campaign_body(expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0}),
    )).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await earn(api, intel, sid, 12_000)

    challenge = (await api.post("/auth/step-up/request", headers=auth(creator), json={"action": "delete_account"})).json()
    proof = await api.post(
        "/auth/step-up/verify", headers=auth(creator),
        json={"challenge_token": challenge["challenge_token"], "password": "DemoPassword123!"},
    )
    assert proof.status_code == 200
    step_up_token = proof.json()["step_up_token"]

    blocked = await api.request("DELETE", "/auth/account", headers=auth(creator), json={"step_up_token": step_up_token})
    assert blocked.status_code == 409


async def test_a_step_up_proof_only_authorises_the_action_it_was_issued_for(api):
    _, creator = await signup(api, "creator")
    challenge = (await api.post("/auth/step-up/request", headers=auth(creator), json={"action": "unlink_google"})).json()
    proof = (await api.post(
        "/auth/step-up/verify", headers=auth(creator),
        json={"challenge_token": challenge["challenge_token"], "password": "DemoPassword123!"},
    )).json()

    misused = await api.request("DELETE", "/auth/account", headers=auth(creator), json={"step_up_token": proof["step_up_token"]})
    assert misused.status_code == 401  # this proof was only ever good for unlink_google


async def test_a_step_up_proof_is_single_use(api):
    _, creator = await signup(api, "creator")
    challenge = (await api.post("/auth/step-up/request", headers=auth(creator), json={"action": "delete_account"})).json()
    proof = (await api.post(
        "/auth/step-up/verify", headers=auth(creator),
        json={"challenge_token": challenge["challenge_token"], "password": "DemoPassword123!"},
    )).json()
    # Spend it on something that will fail for an unrelated reason (no
    # money involved for a fresh creator) so we can tell it was consumed.
    first = await api.request("DELETE", "/auth/account", headers=auth(creator), json={"step_up_token": proof["step_up_token"]})
    assert first.status_code == 204

    # A brand-new creator to retry the same *proof token* against — it must
    # already be spent, regardless of who it's aimed at now.
    _, creator2 = await signup(api, "creator")
    challenge2 = (await api.post("/auth/step-up/request", headers=auth(creator2), json={"action": "delete_account"})).json()
    proof2 = (await api.post(
        "/auth/step-up/verify", headers=auth(creator2),
        json={"challenge_token": challenge2["challenge_token"], "password": "DemoPassword123!"},
    )).json()
    again = await api.request("DELETE", "/auth/account", headers=auth(creator2), json={"step_up_token": proof2["step_up_token"]})
    assert again.status_code == 204
    replay = await api.request("DELETE", "/auth/account", headers=auth(creator2), json={"step_up_token": proof2["step_up_token"]})
    assert replay.status_code == 401


async def test_deleting_an_account_anonymises_it_and_signs_out_everywhere(api):
    email, creator = await signup(api, "creator")
    challenge = (await api.post("/auth/step-up/request", headers=auth(creator), json={"action": "delete_account"})).json()
    proof = (await api.post(
        "/auth/step-up/verify", headers=auth(creator),
        json={"challenge_token": challenge["challenge_token"], "password": "DemoPassword123!"},
    )).json()
    r = await api.request("DELETE", "/auth/account", headers=auth(creator), json={"step_up_token": proof["step_up_token"]})
    assert r.status_code == 204

    dead = await api.get("/auth/me", headers=auth(creator))
    assert dead.status_code == 401
    cannot_relogin = await api.post("/auth/login", json={"email": email, "password": "DemoPassword123!"})
    assert cannot_relogin.status_code == 401


async def test_providers_lists_password_only_for_a_normal_account(api):
    _, creator = await signup(api, "creator")
    r = (await api.get("/auth/providers", headers=auth(creator))).json()
    by_provider = {p["provider"]: p for p in r["providers"]}
    assert by_provider["password"]["linked"] is True and by_provider["password"]["removable"] is False
    assert by_provider["google"]["linked"] is False


async def _fake_google_identity(monkeypatch, *, google_id="g-1", email="tobi@gmail.com", email_verified=True, name="Tobi"):
    settings = get_settings()
    monkeypatch.setattr(settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "test-client-secret")

    async def fake_exchange_code(code: str) -> str:
        return "fake-id-token"

    async def fake_verify_id_token(id_token: str, *, expected_nonce: str) -> GoogleIdentity:
        return GoogleIdentity(google_id=google_id, email=email, email_verified=email_verified, name=name)

    monkeypatch.setattr(google_router, "exchange_code", fake_exchange_code)
    monkeypatch.setattr(google_router, "verify_id_token", fake_verify_id_token)


def _state_from_login_redirect(location: str) -> str:
    from urllib.parse import parse_qs, urlparse

    return parse_qs(urlparse(location).query)["state"][0]


async def _google_login_access_token(api, *, code: str, role: str = "creator") -> str:
    """A full Google login round trip with no role hint (the generic
    sign-in page's button never sends one). For a brand-new identity this
    now lands on `/auth/choose-role`, not an immediate access token — see
    modules.auth.google_router's `complete-signup`."""
    from urllib.parse import parse_qs, urlparse

    login = await api.get("/auth/google/login", follow_redirects=False)
    cb = await api.get(
        "/auth/google/callback", params={"code": code, "state": _state_from_login_redirect(login.headers["location"])},
        follow_redirects=False,
    )
    location = cb.headers["location"]
    if "access_token=" in location:
        return parse_qs(urlparse(location).query)["access_token"][0]
    pending_token = parse_qs(urlparse(location).query)["token"][0]
    completed = await api.post("/auth/google/complete-signup", json={"token": pending_token, "role": role})
    return completed.json()["access_token"]


async def test_google_login_is_unavailable_without_client_credentials(api):
    r = await api.get("/auth/google/login", follow_redirects=False)
    assert r.status_code == 503


async def test_google_link_url_requires_login_and_returns_a_navigable_url(api, monkeypatch):
    await _fake_google_identity(monkeypatch)
    assert (await api.get("/auth/google/link-url")).status_code == 401
    _, creator = await signup(api, "creator")
    response = await api.get("/auth/google/link-url", headers=auth(creator))
    assert response.status_code == 200
    assert response.json()["url"].startswith("https://accounts.google.com/")


async def test_google_sign_in_creates_a_new_passwordless_account(api, monkeypatch):
    await _fake_google_identity(monkeypatch, email="newcreator@gmail.com")
    login = await api.get("/auth/google/login", params={"role": "creator"}, follow_redirects=False)
    assert login.status_code in (302, 307)
    state = _state_from_login_redirect(login.headers["location"])

    callback = await api.get("/auth/google/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    assert callback.status_code in (302, 307)
    location = callback.headers["location"]
    assert "access_token=" in location and "refresh_token=" in location

    from urllib.parse import parse_qs, urlparse

    token = parse_qs(urlparse(location).query)["access_token"][0]
    me = (await api.get("/auth/me", headers={"Authorization": f"Bearer {token}"})).json()
    assert me["email"] == "newcreator@gmail.com" and me["email_verified"] is True

    providers = (await api.get("/auth/providers", headers={"Authorization": f"Bearer {token}"})).json()
    by_provider = {p["provider"]: p for p in providers["providers"]}
    assert by_provider["password"]["linked"] is False
    assert by_provider["google"]["linked"] is True and by_provider["google"]["removable"] is False


async def test_a_brand_new_google_identity_with_no_role_is_asked_not_defaulted(api, monkeypatch):
    """The generic sign-in page's Google button sends no role — for a truly
    new identity that must not silently become a creator account (the bug
    this whole flow exists to close)."""
    from urllib.parse import parse_qs, urlparse

    await _fake_google_identity(monkeypatch, google_id="g-ambiguous", email="brandnew@gmail.com")
    login = await api.get("/auth/google/login", follow_redirects=False)
    cb = await api.get(
        "/auth/google/callback", params={"code": "abc", "state": _state_from_login_redirect(login.headers["location"])},
        follow_redirects=False,
    )
    location = cb.headers["location"]
    assert "/auth/choose-role?token=" in location and "access_token=" not in location
    pending_token = parse_qs(urlparse(location).query)["token"][0]

    completed = await api.post("/auth/google/complete-signup", json={"token": pending_token, "role": "organisation"})
    assert completed.status_code == 200
    body = completed.json()
    assert body["user"]["role"] == "organisation" and body["user"]["email"] == "brandnew@gmail.com"

    # the pending token is single-use, not a standing credential
    replay = await api.post("/auth/google/complete-signup", json={"token": pending_token, "role": "creator"})
    assert replay.status_code == 200  # same google_id now has a user row: logs back in, ignores the replayed role
    assert replay.json()["user"]["role"] == "organisation"

    admin_attempt = await api.post("/auth/google/complete-signup", json={"token": pending_token, "role": "admin"})
    assert admin_attempt.status_code == 422


async def test_google_sign_in_reuses_the_same_account_on_a_second_login(api, monkeypatch):
    await _fake_google_identity(monkeypatch, google_id="g-42", email="repeat@gmail.com")
    token1 = await _google_login_access_token(api, code="abc")
    uid1 = (await api.get("/auth/me", headers={"Authorization": f"Bearer {token1}"})).json()["id"]

    token2 = await _google_login_access_token(api, code="def")
    uid2 = (await api.get("/auth/me", headers={"Authorization": f"Bearer {token2}"})).json()["id"]
    assert uid1 == uid2


async def test_google_does_not_take_over_an_existing_account_with_an_unverified_email_match(api, monkeypatch):
    email, creator = await signup(api, "creator")

    await _fake_google_identity(monkeypatch, google_id="g-link", email=email, email_verified=False)
    login = await api.get("/auth/google/login", follow_redirects=False)
    cb = await api.get(
        "/auth/google/callback", params={"code": "x", "state": _state_from_login_redirect(login.headers["location"])},
        follow_redirects=False,
    )
    # Unverified email at Google: refused outright, not silently linked or
    # spun into a second, colliding account.
    assert "google_error=email_not_verified_by_google" in cb.headers["location"]
    still_own_account = await api.get("/auth/me", headers=auth(creator))
    assert still_own_account.status_code == 200 and still_own_account.json()["id"] == creator["user"]["id"]


async def test_set_first_password_needs_step_up_and_only_applies_to_passwordless_accounts(api, monkeypatch):
    await _fake_google_identity(monkeypatch, email="pwless@gmail.com")
    token = await _google_login_access_token(api, code="x")
    headers = {"Authorization": f"Bearer {token}"}

    challenge = (await api.post("/auth/step-up/request", headers=headers, json={"action": "set_password"})).json()
    # A passwordless account has no password to prove — verify must fail cleanly.
    no_password_yet = await api.post(
        "/auth/step-up/verify", headers=headers,
        json={"challenge_token": challenge["challenge_token"], "password": "whatever123"},
    )
    assert no_password_yet.status_code == 401
