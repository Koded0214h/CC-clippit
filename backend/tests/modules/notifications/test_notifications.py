import pytest

from core.database import Base  # noqa: F401
from modules.notifications import service
from tests.http_app import api, signup  # noqa: F401


def _auth(body):
    return {"Authorization": f"Bearer {body['access_token']}"}


async def _notify(api, user_id, kind, title="Hello", body=""):
    """Drive `notify()` the way another module would, through the app's own
    session dependency override."""
    from core.deps import get_db
    from main import app

    async for db in app.dependency_overrides[get_db]():
        note = await service.notify(db, user_id, kind, title, body, link="/dashboard/earnings")
        await db.commit()
        return note


async def test_inbox_lists_newest_first_with_unread_count(api):
    _, cr = await signup(api, "creator")
    uid = cr["user"]["id"]
    import uuid

    await _notify(api, uuid.UUID(uid), "payout", "First")
    await _notify(api, uuid.UUID(uid), "payout", "Second")
    r = await api.get("/notifications", headers=_auth(cr))
    assert r.status_code == 200
    out = r.json()
    assert out["unread_count"] == 2
    assert [n["title"] for n in out["items"]] == ["Second", "First"]
    assert out["items"][0]["link"] == "/dashboard/earnings" and out["items"][0]["read"] is False


async def test_mark_one_and_all_read(api):
    _, cr = await signup(api, "creator")
    import uuid

    uid = uuid.UUID(cr["user"]["id"])
    a = await _notify(api, uid, "payout", "A")
    await _notify(api, uid, "payout", "B")
    r = await api.post(f"/notifications/{a.id}/read", headers=_auth(cr))
    assert r.json()["read"] is True
    assert (await api.get("/notifications", headers=_auth(cr))).json()["unread_count"] == 1
    assert (await api.post("/notifications/read-all", headers=_auth(cr))).status_code == 204
    out = (await api.get("/notifications?unread_only=true", headers=_auth(cr))).json()
    assert out["unread_count"] == 0 and out["items"] == []


async def test_cannot_read_someone_elses_notification(api):
    _, alice = await signup(api, "creator")
    _, bob = await signup(api, "creator")
    import uuid

    note = await _notify(api, uuid.UUID(alice["user"]["id"]), "payout", "Private")
    assert (await api.post(f"/notifications/{note.id}/read", headers=_auth(bob))).status_code == 404
    assert (await api.get("/notifications", headers=_auth(bob))).json()["items"] == []


async def test_toggle_off_suppresses_the_notification(api):
    _, cr = await signup(api, "creator")
    import uuid

    uid = uuid.UUID(cr["user"]["id"])
    await api.patch("/profile/preferences", headers=_auth(cr), json={"notifications": {"submission_verdicts": False}})
    assert await _notify(api, uid, "submission_verdict", "Verdict") is None
    assert (await api.get("/notifications", headers=_auth(cr))).json()["items"] == []


async def test_money_outcomes_ignore_the_toggles(api):
    _, cr = await signup(api, "creator")
    import uuid

    uid = uuid.UUID(cr["user"]["id"])
    await api.patch(
        "/profile/preferences",
        headers=_auth(cr),
        json={"email_notifications": False, "notifications": {"earnings_payable": False}},
    )
    assert await _notify(api, uid, "payout", "Transfer sent") is not None


async def test_notification_settings_merge_and_default(api):
    _, cr = await signup(api, "creator")
    prefs = (await api.get("/profile/preferences", headers=_auth(cr))).json()
    assert prefs["notifications"]["new_campaigns"] is True
    assert prefs["notifications"]["campaign_closing"] is False

    r = await api.patch("/profile/preferences", headers=_auth(cr), json={"notifications": {"campaign_closing": True}})
    assert r.json()["notifications"]["campaign_closing"] is True
    r = await api.patch("/profile/preferences", headers=_auth(cr), json={"notifications": {"new_campaigns": False}})
    n = r.json()["notifications"]
    assert n["new_campaigns"] is False and n["campaign_closing"] is True  # earlier change kept


async def test_unread_count_is_cheap_and_excludes_archived(api):
    import uuid

    _, cr = await signup(api, "creator")
    uid = uuid.UUID(cr["user"]["id"])
    n1 = await _notify(api, uid, "payout", "First")
    await _notify(api, uid, "payout", "Second")

    before_archive = await api.get("/notifications/unread-count", headers=_auth(cr))
    assert before_archive.json() == {"unread_count": 2}

    archived = await api.post(f"/notifications/{n1.id}/archive", headers=_auth(cr))
    assert archived.status_code == 204
    after_archive = await api.get("/notifications/unread-count", headers=_auth(cr))
    assert after_archive.json() == {"unread_count": 1}

    inbox = (await api.get("/notifications", headers=_auth(cr))).json()
    assert len(inbox["items"]) == 1 and inbox["unread_count"] == 1  # archived one is hidden, not just unread


async def test_archiving_someone_elses_notification_is_404(api):
    import uuid

    _, cr = await signup(api, "creator")
    _, other = await signup(api, "creator")
    n = await _notify(api, uuid.UUID(cr["user"]["id"]), "payout", "Mine")
    r = await api.post(f"/notifications/{n.id}/archive", headers=_auth(other))
    assert r.status_code == 404


async def test_push_subscriptions_register_update_and_remove(api):
    _, cr = await signup(api, "creator")
    body = {"endpoint": "https://push.example/abc", "p256dh_key": "key1", "auth_key": "auth1"}

    first = await api.post("/push-subscriptions", headers=_auth(cr), json=body)
    assert first.status_code == 201
    sub_id = first.json()["id"]

    # Re-registering the same endpoint updates in place, not duplicates.
    again = await api.post("/push-subscriptions", headers=_auth(cr), json={**body, "p256dh_key": "key2"})
    assert again.status_code == 201 and again.json()["id"] == sub_id

    gone = await api.delete(f"/push-subscriptions/{sub_id}", headers=_auth(cr))
    assert gone.status_code == 204
    twice = await api.delete(f"/push-subscriptions/{sub_id}", headers=_auth(cr))
    assert twice.status_code == 404


async def test_a_creator_cannot_remove_someone_elses_push_subscription(api):
    _, cr = await signup(api, "creator")
    _, other = await signup(api, "creator")
    sub = (await api.post(
        "/push-subscriptions", headers=_auth(cr),
        json={"endpoint": "https://push.example/xyz", "p256dh_key": "k", "auth_key": "a"},
    )).json()
    r = await api.delete(f"/push-subscriptions/{sub['id']}", headers=_auth(other))
    assert r.status_code == 404
