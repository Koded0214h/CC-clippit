"""Financial disputes and safety reports (production-api-inventory.md
§L)."""

import pytest

from tests.http_app import (
    api, approve_clip, auth, campaign_body, earn, fund_campaign, intel, make_admin, make_creator, signup, submit_clip,
)


async def _earning_entry(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post(
        "/campaigns", headers=auth(org),
        json=campaign_body(expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0}),
    )).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await approve_clip(api, org, sid)
    await earn(api, intel, sid, 12_000)  # ₦6,000
    entry_id = (await api.get("/earnings/history", headers=auth(creator))).json()["items"][0]["id"]
    return creator, org, entry_id


async def test_opening_a_dispute_captures_the_amount_at_risk(api, intel):
    creator, org, entry_id = await _earning_entry(api, intel)
    r = await api.post(
        "/disputes", headers=auth(creator),
        json={"type": "earning_entry", "resource_id": entry_id, "reason": "This clip earned way less than my views should have."},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["amount_at_risk"] == 6000 and body["status"] == "open" and len(body["messages"]) == 0


async def test_a_resource_that_is_not_yours_cannot_be_disputed(api, intel):
    creator, org, entry_id = await _earning_entry(api, intel)
    intruder = await make_creator(api, handle="@intruder")
    r = await api.post(
        "/disputes", headers=auth(intruder),
        json={"type": "earning_entry", "resource_id": entry_id, "reason": "Not mine but I want to try disputing it anyway."},
    )
    assert r.status_code == 404


async def test_cannot_open_two_open_disputes_on_the_same_entry(api, intel):
    creator, org, entry_id = await _earning_entry(api, intel)
    body = {"type": "earning_entry", "resource_id": entry_id, "reason": "First dispute about this earning entry amount."}
    first = await api.post("/disputes", headers=auth(creator), json=body)
    assert first.status_code == 201
    second = await api.post("/disputes", headers=auth(creator), json=body)
    assert second.status_code == 409


async def test_a_creator_message_reopens_a_dispute_awaiting_them(api, intel):
    creator, org, entry_id = await _earning_entry(api, intel)
    admin = await make_admin(api)
    dispute = (await api.post(
        "/disputes", headers=auth(creator),
        json={"type": "earning_entry", "resource_id": entry_id, "reason": "This clip earned way less than expected."},
    )).json()

    await api.patch(f"/admin/disputes/{dispute['id']}", headers=auth(admin), json={"status": "awaiting_customer"})
    replied = await api.post(f"/disputes/{dispute['id']}/messages", headers=auth(creator), json={"body": "Here's more detail."})
    assert replied.status_code == 201 and replied.json()["status"] == "open"


async def test_resolving_a_dispute_records_the_decision_without_side_effects(api, intel):
    creator, org, entry_id = await _earning_entry(api, intel)
    admin = await make_admin(api)
    dispute = (await api.post(
        "/disputes", headers=auth(creator),
        json={"type": "earning_entry", "resource_id": entry_id, "reason": "This clip earned way less than expected."},
    )).json()

    resolved = await api.post(
        f"/admin/disputes/{dispute['id']}/resolve", headers=auth(admin),
        json={"resolution": "denied", "note": "Views were verified correctly; amount stands."},
    )
    assert resolved.status_code == 200
    body = resolved.json()
    assert body["status"] == "resolved" and body["resolution"] == "denied" and body["resolved_at"] is not None

    already = await api.post(
        f"/admin/disputes/{dispute['id']}/resolve", headers=auth(admin), json={"resolution": "upheld", "note": "x"}
    )
    assert already.status_code == 409


async def test_admin_can_reopen_a_resolved_dispute(api, intel):
    creator, org, entry_id = await _earning_entry(api, intel)
    admin = await make_admin(api)
    dispute = (await api.post(
        "/disputes", headers=auth(creator),
        json={"type": "earning_entry", "resource_id": entry_id, "reason": "This clip earned way less than expected."},
    )).json()
    await api.post(f"/admin/disputes/{dispute['id']}/resolve", headers=auth(admin), json={"resolution": "denied", "note": "x"})

    reopened = await api.post(f"/admin/disputes/{dispute['id']}/reopen", headers=auth(admin))
    assert reopened.status_code == 200 and reopened.json()["status"] == "open"


async def test_the_opener_can_withdraw_their_own_dispute(api, intel):
    creator, org, entry_id = await _earning_entry(api, intel)
    dispute = (await api.post(
        "/disputes", headers=auth(creator),
        json={"type": "earning_entry", "resource_id": entry_id, "reason": "This clip earned way less than expected."},
    )).json()
    r = await api.post(f"/disputes/{dispute['id']}/withdraw", headers=auth(creator))
    assert r.status_code == 200 and r.json()["status"] == "withdrawn"


async def test_a_non_admin_cannot_reach_the_dispute_queue(api, intel):
    creator, org, entry_id = await _earning_entry(api, intel)
    r = await api.get("/admin/disputes", headers=auth(creator))
    assert r.status_code == 403


async def test_disputing_an_old_payout_is_refused_by_the_filing_window(api, intel):
    from datetime import datetime, timedelta, timezone

    import uuid as _uuid

    from modules.payouts.models import Payout
    from tests.http_app import clear_hold, db_session

    creator, org, entry_id = await _earning_entry(api, intel)
    await clear_hold(creator["user"]["id"])
    await api.put("/creators/me/bank-details", headers=auth(creator), json={"bank_code": "058", "bank_name": "GTBank", "account_number": "0123456789"})
    await api.post("/creators/me/bank-details/verify", headers=auth(creator))
    payout = (await api.post("/payouts", headers=auth(creator), json={"amount": 5000, "idempotency_key": "dispute-test-1"})).json()

    async with db_session() as db:
        row = await db.get(Payout, _uuid.UUID(payout["id"]))
        row.completed_at = datetime.now(timezone.utc) - timedelta(days=30)
        await db.commit()

    r = await api.post(
        "/disputes", headers=auth(creator),
        json={"type": "payout", "resource_id": payout["id"], "reason": "This payout amount looks wrong to me."},
    )
    assert r.status_code == 409


async def test_filing_a_report_and_the_reporter_seeing_only_their_own(api):
    _, reporter = await signup(api, "creator")
    _, someone_else = await signup(api, "creator")
    import uuid

    target_id = uuid.uuid4()
    r = await api.post(
        "/reports", headers=auth(reporter),
        json={"target_type": "campaign", "target_id": str(target_id), "reason": "spam", "details": "Looks like a scam campaign."},
    )
    assert r.status_code == 201
    assert "reporter_id" not in r.json()  # customer-safe shape

    mine = (await api.get("/reports/me", headers=auth(reporter))).json()
    assert len(mine) == 1
    theirs = (await api.get("/reports/me", headers=auth(someone_else))).json()
    assert theirs == []


async def test_admin_resolves_a_report_with_a_structured_outcome(api):
    _, reporter = await signup(api, "creator")
    admin = await make_admin(api)
    import uuid

    report = (await api.post(
        "/reports", headers=auth(reporter),
        json={"target_type": "creator_profile", "target_id": str(uuid.uuid4()), "reason": "impersonation"},
    )).json()

    queue = await api.get("/admin/reports", headers=auth(admin), params={"target_type": "creator_profile"})
    assert queue.status_code == 200 and len(queue.json()) == 1
    assert queue.json()[0]["reporter_id"] == reporter["user"]["id"]  # visible to admin, not the customer endpoint

    resolved = await api.post(
        f"/admin/reports/{report['id']}/resolve", headers=auth(admin),
        json={"resolution": "account_sanctioned", "note": "Confirmed impersonation, account suspended separately."},
    )
    assert resolved.status_code == 200 and resolved.json()["status"] == "resolved"

    again = await api.post(
        f"/admin/reports/{report['id']}/resolve", headers=auth(admin), json={"resolution": "no_action", "note": "x"}
    )
    assert again.status_code == 409


async def test_a_non_admin_cannot_reach_the_report_queue(api):
    _, reporter = await signup(api, "creator")
    r = await api.get("/admin/reports", headers=auth(reporter))
    assert r.status_code == 403
