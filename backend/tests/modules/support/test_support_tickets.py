"""Customer support tickets and the operator queue
(production-api-inventory.md §K)."""

import pytest

from tests.http_app import api, auth, make_admin, signup


async def test_creating_a_ticket_starts_the_thread_with_the_first_message(api):
    _, creator = await signup(api, "creator")
    r = await api.post(
        "/support/tickets", headers=auth(creator),
        json={"category": "payouts", "subject": "Withdrawal stuck", "message": "It's been three days."},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "open" and body["unread_count"] == 0
    assert len(body["messages"]) == 1 and body["messages"][0]["body"] == "It's been three days."


async def test_a_customer_sees_only_their_own_tickets(api):
    _, mine = await signup(api, "creator")
    _, theirs = await signup(api, "creator")
    await api.post("/support/tickets", headers=auth(mine), json={"category": "x", "subject": "Mine", "message": "hi"})
    await api.post("/support/tickets", headers=auth(theirs), json={"category": "x", "subject": "Theirs", "message": "hi"})

    mine_list = (await api.get("/support/tickets", headers=auth(mine))).json()
    assert [t["subject"] for t in mine_list] == ["Mine"]


async def test_an_admin_reply_shows_as_unread_until_the_customer_reads_it(api):
    _, creator = await signup(api, "creator")
    admin = await make_admin(api)
    ticket = (await api.post(
        "/support/tickets", headers=auth(creator), json={"category": "x", "subject": "Help", "message": "hi"}
    )).json()

    await api.post(f"/admin/support/tickets/{ticket['id']}/messages", headers=auth(admin), json={"body": "Looking into it"})

    unread = (await api.get("/support/tickets", headers=auth(creator))).json()
    assert unread[0]["unread_count"] == 1

    opened = (await api.get(f"/support/tickets/{ticket['id']}", headers=auth(creator))).json()
    assert opened["unread_count"] == 0 and len(opened["messages"]) == 2

    after_read = (await api.get("/support/tickets", headers=auth(creator))).json()
    assert after_read[0]["unread_count"] == 0


async def test_replying_reopens_a_closed_ticket(api):
    _, creator = await signup(api, "creator")
    ticket = (await api.post(
        "/support/tickets", headers=auth(creator), json={"category": "x", "subject": "Help", "message": "hi"}
    )).json()
    await api.post(f"/support/tickets/{ticket['id']}/close", headers=auth(creator))

    replied = await api.post(f"/support/tickets/{ticket['id']}/messages", headers=auth(creator), json={"body": "Actually still broken"})
    assert replied.status_code == 201 and replied.json()["status"] == "open"


async def test_only_the_ticket_owner_can_close_or_reply(api):
    _, creator = await signup(api, "creator")
    _, stranger = await signup(api, "creator")
    ticket = (await api.post(
        "/support/tickets", headers=auth(creator), json={"category": "x", "subject": "Help", "message": "hi"}
    )).json()

    denied_close = await api.post(f"/support/tickets/{ticket['id']}/close", headers=auth(stranger))
    assert denied_close.status_code == 404  # doesn't confirm the ticket exists to a stranger

    denied_reply = await api.post(f"/support/tickets/{ticket['id']}/messages", headers=auth(stranger), json={"body": "hey"})
    assert denied_reply.status_code == 404


async def test_admin_queue_filters_and_operator_notes_stay_internal(api):
    _, creator = await signup(api, "creator")
    admin = await make_admin(api)
    ticket = (await api.post(
        "/support/tickets", headers=auth(creator), json={"category": "billing", "subject": "Refund?", "message": "hi"}
    )).json()

    queue = await api.get("/admin/support/tickets", headers=auth(admin), params={"category": "billing"})
    assert queue.status_code == 200 and len(queue.json()) == 1

    empty = await api.get("/admin/support/tickets", headers=auth(admin), params={"category": "payouts"})
    assert empty.json() == []

    note = await api.post(f"/admin/support/tickets/{ticket['id']}/notes", headers=auth(admin), json={"body": "Looks legit, approving"})
    assert note.status_code == 201

    admin_view = (await api.get(f"/admin/support/tickets/{ticket['id']}", headers=auth(admin))).json()
    assert admin_view["notes"][0]["body"] == "Looks legit, approving"
    assert admin_view["customer_role"] == "creator"

    customer_view = (await api.get(f"/support/tickets/{ticket['id']}", headers=auth(creator))).json()
    assert "notes" not in customer_view


async def test_admin_can_assign_and_change_priority_and_status(api):
    _, creator = await signup(api, "creator")
    admin = await make_admin(api)
    ticket = (await api.post(
        "/support/tickets", headers=auth(creator), json={"category": "x", "subject": "Help", "message": "hi"}
    )).json()

    patched = await api.patch(
        f"/admin/support/tickets/{ticket['id']}", headers=auth(admin),
        json={"priority": "urgent", "assignee_id": admin["user"]["id"], "status": "closed"},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["priority"] == "urgent" and body["assignee_id"] == admin["user"]["id"]
    assert body["status"] == "closed" and body["closed_at"] is not None


async def test_a_non_admin_cannot_reach_the_operator_queue(api):
    _, creator = await signup(api, "creator")
    r = await api.get("/admin/support/tickets", headers=auth(creator))
    assert r.status_code == 403


async def test_reopen_is_refused_after_the_window_but_not_before(api):
    _, creator = await signup(api, "creator")
    ticket = (await api.post(
        "/support/tickets", headers=auth(creator), json={"category": "x", "subject": "Help", "message": "hi"}
    )).json()
    await api.post(f"/support/tickets/{ticket['id']}/close", headers=auth(creator))

    reopened = await api.post(f"/support/tickets/{ticket['id']}/reopen", headers=auth(creator))
    assert reopened.status_code == 200 and reopened.json()["status"] == "open"

    # Can't reopen a ticket that's already open.
    await api.post(f"/support/tickets/{ticket['id']}/close", headers=auth(creator))
    from datetime import datetime, timedelta, timezone

    from tests.http_app import db_session
    from modules.support.models import SupportTicket
    import uuid as _uuid

    async with db_session() as db:
        row = await db.get(SupportTicket, _uuid.UUID(ticket["id"]))
        row.closed_at = datetime.now(timezone.utc) - timedelta(days=30)
        await db.commit()

    too_late = await api.post(f"/support/tickets/{ticket['id']}/reopen", headers=auth(creator))
    assert too_late.status_code == 409
