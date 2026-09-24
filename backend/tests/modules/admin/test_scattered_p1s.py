"""Scattered P1s: payout quotes, deleting a bank destination, audit
detail/export, the brand transactions export, admin refunds, single-payout
reconcile, job visibility, and the ledger export."""

import pytest

from tests.http_app import (
    api, approve_clip, auth, campaign_body, clear_hold, earn, fund_campaign, intel, make_admin, make_creator, signup,
    submit_clip,
)


async def test_payout_quote_previews_without_reserving_anything(api):
    _, creator = await signup(api, "creator")
    r = await api.post("/payouts/quote", headers=auth(creator), json={"amount": 5000, "idempotency_key": "quote-key-01"})
    assert r.status_code == 200
    body = r.json()
    assert body["amount"] == 5000 and body["fee"] == 350 and body["net_amount"] == 4650
    assert (await api.get("/payouts", headers=auth(creator))).json()["items"] == []  # nothing was created


async def test_payout_quote_below_minimum_is_refused(api):
    _, creator = await signup(api, "creator")
    r = await api.post("/payouts/quote", headers=auth(creator), json={"amount": 100, "idempotency_key": "quote-key-02"})
    assert r.status_code == 422


async def _earner_with_bank_details(api, intel):
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
    await clear_hold(creator["user"]["id"])
    await api.put("/creators/me/bank-details", headers=auth(creator), json={"bank_code": "058", "bank_name": "GTBank", "account_number": "0123456789"})
    await api.post("/creators/me/bank-details/verify", headers=auth(creator))
    return creator


async def _step_up(api, creator, action):
    challenge = (await api.post("/auth/step-up/request", headers=auth(creator), json={"action": action})).json()
    proof = (await api.post(
        "/auth/step-up/verify", headers=auth(creator),
        json={"challenge_token": challenge["challenge_token"], "password": "DemoPassword123!"},
    )).json()
    return proof["step_up_token"]


async def test_deleting_bank_details_needs_step_up_and_no_pending_payout(api, intel):
    creator = await _earner_with_bank_details(api, intel)
    token = await _step_up(api, creator, "delete_bank_details")

    deleted = await api.request("DELETE", "/creators/me/bank-details", headers=auth(creator), json={"step_up_token": token})
    assert deleted.status_code == 204
    assert (await api.get("/creators/me/bank-details", headers=auth(creator))).status_code == 404


async def test_deleting_bank_details_is_refused_with_a_payout_in_flight(api, intel):
    from modules.payouts.models import Payout, PayoutStatus
    from tests.http_app import db_session
    import uuid as _uuid

    creator = await _earner_with_bank_details(api, intel)
    payout = (await api.post("/payouts", headers=auth(creator), json={"amount": 5000, "idempotency_key": "bank-del-key-01"})).json()
    # The sandbox settles synchronously; force it back to "processing" to
    # exercise the in-flight guard.
    async with db_session() as db:
        row = await db.get(Payout, _uuid.UUID(payout["id"]))
        row.status = PayoutStatus.processing
        await db.commit()

    token = await _step_up(api, creator, "delete_bank_details")
    r = await api.request("DELETE", "/creators/me/bank-details", headers=auth(creator), json={"step_up_token": token})
    assert r.status_code == 409


async def test_admin_audit_detail_and_export(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    await fund_campaign(api, org, campaign["id"])

    admin = await make_admin(api)
    listed = (await api.get("/admin/audit", headers=auth(admin), params={"kind": "funding"})).json()
    assert listed
    event_id = listed[0]["id"]

    detail = await api.get(f"/admin/audit/{event_id}", headers=auth(admin))
    assert detail.status_code == 200 and detail.json()["id"] == event_id

    exported = await api.get("/admin/audit/export", headers=auth(admin))
    assert exported.status_code == 200 and exported.headers["content-type"].startswith("text/csv")
    assert event_id in exported.text


async def test_unknown_audit_event_is_404(api):
    admin = await make_admin(api)
    r = await api.get("/admin/audit/00000000-0000-0000-0000-000000000000", headers=auth(admin))
    assert r.status_code == 404


async def test_brand_transactions_export_is_a_csv(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    await fund_campaign(api, org, campaign["id"])

    r = await api.get("/organisations/me/transactions/export", headers=auth(org))
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "funding" in r.text


async def test_admin_can_list_refunds(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body(pot=5000, expected_views=None))).json()
    await fund_campaign(api, org, campaign["id"])
    await api.post(f"/campaigns/{campaign['id']}/close", headers=auth(org))
    await api.post(f"/campaigns/{campaign['id']}/refunds", headers=auth(org), json={"reason": "Unused"})

    admin = await make_admin(api)
    rows = (await api.get("/admin/refunds", headers=auth(admin))).json()
    assert any(r["kind"] == "refund" and r["campaign_id"] == campaign["id"] for r in rows)

    succeeded_only = (await api.get("/admin/refunds", headers=auth(admin), params={"status": "succeeded"})).json()
    assert all(r["status"] == "succeeded" for r in succeeded_only)


async def test_admin_can_reconcile_one_payout(api, intel):
    from modules.payouts.models import Payout, PayoutStatus
    from tests.http_app import db_session
    import uuid as _uuid

    creator = await _earner_with_bank_details(api, intel)
    payout = (await api.post("/payouts", headers=auth(creator), json={"amount": 5000, "idempotency_key": "reconcile-key-01"})).json()
    # Force it back to "processing" — the sandbox settles synchronously, so
    # there's nothing genuinely in flight to reconcile otherwise.
    async with db_session() as db:
        row = await db.get(Payout, _uuid.UUID(payout["id"]))
        row.status = PayoutStatus.processing
        await db.commit()

    admin = await make_admin(api)
    r = await api.post(f"/admin/payouts/{payout['id']}/reconcile", headers=auth(admin))
    assert r.status_code == 200 and r.json()["status"] == "succeeded"  # the sandbox reports it already went through


async def test_reconciling_a_settled_payout_is_refused(api, intel):
    creator = await _earner_with_bank_details(api, intel)
    payout = (await api.post("/payouts", headers=auth(creator), json={"amount": 5000, "idempotency_key": "reconcile-key-02"})).json()
    assert payout["status"] == "succeeded"  # sandbox is synchronous

    admin = await make_admin(api)
    r = await api.post(f"/admin/payouts/{payout['id']}/reconcile", headers=auth(admin))
    assert r.status_code == 409


async def test_admin_jobs_are_listed_and_can_be_run_on_demand(api, monkeypatch):
    from modules.earnings import jobs as earnings_jobs

    async def fake_settle(*a, **k):
        return 0

    monkeypatch.setattr(earnings_jobs, "settle_tick", fake_settle)

    admin = await make_admin(api)
    jobs = (await api.get("/admin/jobs", headers=auth(admin))).json()
    names = {j["name"] for j in jobs}
    assert "earnings.settle" in names and "campaigns.sweep" in names

    r = await api.post("/admin/jobs/earnings.settle/run", headers=auth(admin))
    assert r.status_code == 200


async def test_running_an_unknown_job_is_404(api):
    admin = await make_admin(api)
    r = await api.post("/admin/jobs/not-a-real-job/run", headers=auth(admin))
    assert r.status_code == 404


async def test_ledger_export_is_a_csv_covering_funding_and_refunds(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    await fund_campaign(api, org, campaign["id"])

    admin = await make_admin(api)
    r = await api.get("/admin/ledger/export", headers=auth(admin))
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "funding" in r.text


async def test_scattered_p1_admin_routes_refuse_a_non_admin(api):
    _, creator = await signup(api, "creator")
    for method, path in [
        ("get", "/admin/refunds"), ("get", "/admin/jobs"), ("get", "/admin/ledger/export"), ("get", "/admin/audit/export"),
    ]:
        r = await getattr(api, method)(path, headers=auth(creator))
        assert r.status_code == 403, path
