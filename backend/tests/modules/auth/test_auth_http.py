from tests.http_app import api, signup  # noqa: F401


async def test_signup_login_and_me(api):
    email, body = await signup(api, "creator")
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "creator"
    token = body["access_token"]

    me = await api.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email

    login = await api.post("/auth/login", json={"email": email, "password": "DemoPassword123!"})
    assert login.status_code == 200


async def test_bad_password_is_rejected(api):
    email, _ = await signup(api, "organisation")
    r = await api.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert r.status_code == 401


async def test_cannot_self_signup_as_admin(api):
    r = await api.post(
        "/auth/signup",
        json={
            "email": "admin@example.com",
            "password": "DemoPassword123!",
            "full_name": "Nope",
            "role": "admin",
        },
    )
    assert r.status_code == 422
