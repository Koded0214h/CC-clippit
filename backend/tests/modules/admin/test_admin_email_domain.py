"""require_admin also checks the admin's own email domain — a role flipped
by hand in the database still can't reach /admin/* from outside the
company domain. Disabled (empty) by default in tests; these turn it on."""

from sqlalchemy import update

from core.config import get_settings
from modules.auth.models import Role, User
from tests.http_app import api, auth, db_session, make_admin, signup


async def test_an_admin_outside_the_domain_is_refused(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_email_domain", "@clippit.click")
    admin = await make_admin(api)  # make_admin signs up @example.com
    r = await api.get("/admin/overview", headers=auth(admin))
    assert r.status_code == 403


async def test_an_admin_inside_the_domain_is_allowed(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_email_domain", "@clippit.click")
    email, _ = await signup(api, "creator")
    async with db_session() as db:
        await db.execute(update(User).where(User.email == email).values(role=Role.admin, email="ops@clippit.click"))
        await db.commit()
    login = await api.post("/auth/login", json={"email": "ops@clippit.click", "password": "DemoPassword123!"})
    assert login.status_code == 200
    r = await api.get("/admin/overview", headers=auth(login.json()))
    assert r.status_code == 200


async def test_domain_check_is_off_by_default_in_tests(api):
    admin = await make_admin(api)
    assert (await api.get("/admin/overview", headers=auth(admin))).status_code == 200


async def _make_domain_admin(api):
    email, _ = await signup(api, "creator")
    async with db_session() as db:
        await db.execute(update(User).where(User.email == email).values(role=Role.admin, email="inviter@clippit.click"))
        await db.commit()
    login = await api.post("/auth/login", json={"email": "inviter@clippit.click", "password": "DemoPassword123!"})
    login.raise_for_status()
    return login.json()


async def test_inviting_an_operator_outside_the_domain_is_refused(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_email_domain", "@clippit.click")
    admin = await _make_domain_admin(api)
    r = await api.post(
        "/admin/operators/invitations", headers=auth(admin), json={"email": "outsider@gmail.com", "permissions": []}
    )
    assert r.status_code == 422


async def test_inviting_an_operator_inside_the_domain_works(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_email_domain", "@clippit.click")
    admin = await _make_domain_admin(api)
    r = await api.post(
        "/admin/operators/invitations", headers=auth(admin), json={"email": "newops@clippit.click", "permissions": []}
    )
    assert r.status_code == 201
