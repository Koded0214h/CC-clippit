from core.config import get_settings
from tests.http_app import api, latest_code, signup  # noqa: F401


def _auth(body: dict) -> dict:
    return {"Authorization": f"Bearer {body['access_token']}"}


async def test_signup_starts_unverified_and_emails_a_code(api):
    email, body = await signup(api, "creator", verify=False)
    assert body["user"]["email_verified"] is False
    assert body["user"]["onboarding_completed"] is False
    assert len(latest_code(email)) == 6


async def test_verify_email_with_session(api):
    email, body = await signup(api, "creator", verify=False)
    r = await api.post("/auth/verify-email", headers=_auth(body), json={"code": latest_code(email)})
    assert r.status_code == 200
    assert r.json()["email_verified"] is True
    me = await api.get("/auth/me", headers=_auth(body))
    assert me.json()["email_verified"] is True


async def test_verify_email_without_session_needs_the_email(api):
    email, _ = await signup(api, "creator", verify=False)
    code = latest_code(email)
    assert (await api.post("/auth/verify-email", json={"code": code})).status_code == 400
    ok = await api.post("/auth/verify-email", json={"code": code, "email": email})
    assert ok.status_code == 200 and ok.json()["email_verified"] is True


async def test_wrong_code_is_rejected_and_five_wrong_guesses_burn_it(api):
    email, body = await signup(api, "creator", verify=False)
    good = latest_code(email)
    bad = "000000" if good != "000000" else "111111"
    for _ in range(get_settings().otp_max_attempts):
        r = await api.post("/auth/verify-email", headers=_auth(body), json={"code": bad})
        assert r.status_code == 400
    # The right code no longer works: it was burned.
    r = await api.post("/auth/verify-email", headers=_auth(body), json={"code": good})
    assert r.status_code == 400


async def test_code_is_single_use(api):
    email, body = await signup(api, "creator", verify=False)
    code = latest_code(email)
    assert (await api.post("/auth/verify-email", headers=_auth(body), json={"code": code})).status_code == 200
    # Already verified: idempotent success, not an error.
    assert (await api.post("/auth/verify-email", headers=_auth(body), json={"code": code})).status_code == 200


async def test_resend_respects_the_cooldown(api):
    _, body = await signup(api, "creator", verify=False)
    r = await api.post("/auth/verify-email/resend", headers=_auth(body), json={})
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0


async def test_resend_after_cooldown_replaces_the_code(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "otp_resend_cooldown_seconds", 0)
    email, body = await signup(api, "creator", verify=False)
    first = latest_code(email)
    r = await api.post("/auth/verify-email/resend", headers=_auth(body), json={})
    assert r.status_code == 200 and r.json()["resend_in"] == 0
    second = latest_code(email)
    if first != second:  # the old one is dead
        assert (await api.post("/auth/verify-email", headers=_auth(body), json={"code": first})).status_code == 400
    assert (await api.post("/auth/verify-email", headers=_auth(body), json={"code": second})).status_code == 200


async def test_unverified_user_cannot_upload_a_video(api):
    _, body = await signup(api, "creator", verify=False)
    r = await api.post("/uploads/videos", headers=_auth(body), files={"file": ("a.mp4", b"x", "video/mp4")})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "email_not_verified"


# --- password recovery ------------------------------------------------------


async def _recover(api, email: str, new_password: str) -> int:
    assert (await api.post("/auth/forgot-password", json={"email": email})).status_code == 202
    checked = await api.post("/auth/recovery-code/verify", json={"email": email, "code": latest_code(email)})
    assert checked.status_code == 200
    reset = await api.post(
        "/auth/reset-password", json={"reset_token": checked.json()["reset_token"], "password": new_password}
    )
    return reset.status_code


async def test_forgot_password_does_not_reveal_whether_an_account_exists(api):
    r = await api.post("/auth/forgot-password", json={"email": "nobody-here@example.com"})
    assert r.status_code == 202 and r.json()["sent"] is True


async def test_full_recovery_flow_changes_the_password(api):
    email, _ = await signup(api, "creator")
    assert await _recover(api, email, "BrandNewPass456") == 204
    assert (await api.post("/auth/login", json={"email": email, "password": "DemoPassword123!"})).status_code == 401
    assert (await api.post("/auth/login", json={"email": email, "password": "BrandNewPass456"})).status_code == 200


async def test_password_reset_kills_existing_sessions(api):
    email, body = await signup(api, "creator")
    assert (await api.get("/auth/me", headers=_auth(body))).status_code == 200
    import asyncio

    await asyncio.sleep(1.1)  # `iat` has one-second resolution
    assert await _recover(api, email, "BrandNewPass456") == 204
    assert (await api.get("/auth/me", headers=_auth(body))).status_code == 401
    fresh = await api.post("/auth/login", json={"email": email, "password": "BrandNewPass456"})
    assert (await api.get("/auth/me", headers=_auth(fresh.json()))).status_code == 200


async def test_reset_token_is_single_use(api):
    email, _ = await signup(api, "creator")
    await api.post("/auth/forgot-password", json={"email": email})
    token = (
        await api.post("/auth/recovery-code/verify", json={"email": email, "code": latest_code(email)})
    ).json()["reset_token"]
    assert (await api.post("/auth/reset-password", json={"reset_token": token, "password": "FirstNewPass1"})).status_code == 204
    again = await api.post("/auth/reset-password", json={"reset_token": token, "password": "SecondNewPass2"})
    assert again.status_code == 400


async def test_recovery_code_wrong_for_email(api):
    email, _ = await signup(api, "creator")
    await api.post("/auth/forgot-password", json={"email": email})
    r = await api.post("/auth/recovery-code/verify", json={"email": email, "code": "999999"})
    if latest_code(email) != "999999":
        assert r.status_code == 400


async def test_reset_password_rejects_weak_password_and_bad_token(api):
    assert (await api.post("/auth/reset-password", json={"reset_token": "nope", "password": "x"})).status_code == 422
    assert (
        await api.post("/auth/reset-password", json={"reset_token": "nope", "password": "LongEnough1"})
    ).status_code == 400


async def test_recovery_verifies_an_unverified_email(api):
    email, _ = await signup(api, "creator", verify=False)
    assert await _recover(api, email, "BrandNewPass456") == 204
    login = await api.post("/auth/login", json={"email": email, "password": "BrandNewPass456"})
    assert login.json()["user"]["email_verified"] is True
