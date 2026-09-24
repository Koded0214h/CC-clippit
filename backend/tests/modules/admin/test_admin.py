import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from core.config import get_settings
from integrations.payments.base import ProviderError
from integrations.payments.sandbox import SandboxProvider
from modules.funding import models as funding_models
from tests.http_app import (  # noqa: F401
    api, auth, campaign_body, clear_hold, db_session, earn, intel, make_admin, make_creator, open_campaign, signup,
    submit_clip, verified_bank,
)


async def test_every_admin_route_refuses_everyone_else(api, intel):
    _, org = await signup(api, "organisation")
    creator = await make_creator(api)
    routes = [
        ("get", "/admin/overview"), ("get", "/admin/payouts"), ("get", "/admin/funding"), ("get", "/admin/audit"),
        ("get", "/admin/earnings/blocked"), ("post", "/admin/earnings/settle"), ("post", "/admin/campaigns/sweep"),
    ]
    for who in (org, creator):
        for method, path in routes:
            r = await getattr(api, method)(path, headers=auth(who))
            assert r.status_code == 403, (method, path)
    for method, path in routes:
        assert (await getattr(api, method)(path)).status_code == 401


async def test_overview_counts_the_platform(api, intel):
    admin = await make_admin(api)
    _, org = await signup(api, "organisation")
    await open_campaign(api, org)
    o = (await api.get("/admin/overview", headers=auth(admin))).json()
    assert o["users"]["organisation"] == 1 and o["campaigns"]["active"] == 1
    assert o["submissions_needing_review"] == 0 and o["creator_liability"] == 0


async def test_creator_liability_is_what_is_owed_and_not_yet_paid(api, intel):
    admin = await make_admin(api)
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org, expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0})
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await earn(api, intel, sid, 12_000)  # ₦6,000
    assert (await api.get("/admin/overview", headers=auth(admin))).json()["creator_liability"] == 6000
    await clear_hold(creator["user"]["id"])
    await verified_bank(api, creator)
    await api.post("/payouts", headers=auth(creator), json={"amount": 5000, "idempotency_key": "k-liability-1"})
    assert (await api.get("/admin/overview", headers=auth(admin))).json()["creator_liability"] == 1000


async def test_admin_can_list_and_filter_payouts(api, intel):
    admin = await make_admin(api)
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org, expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0})
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await earn(api, intel, sid, 12_000)  # ₦6,000
    await clear_hold(creator["user"]["id"])
    await verified_bank(api, creator)
    await api.post("/payouts", headers=auth(creator), json={"amount": 5000, "idempotency_key": "k-admin-list-1"})

    rows = (await api.get("/admin/payouts", headers=auth(admin))).json()
    assert len(rows) == 1 and rows[0]["status"] == "succeeded" and rows[0]["creator_email"] == creator["user"]["email"]
    assert (await api.get("/admin/payouts?status_filter=failed", headers=auth(admin))).json() == []


async def test_admin_can_retry_and_force_fail_an_in_flight_payout(api, intel, monkeypatch):
    admin = await make_admin(api)
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org, expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0})
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await earn(api, intel, sid, 24_000)  # ₦12,000
    await clear_hold(creator["user"]["id"])
    await verified_bank(api, creator)

    async def down(self, **kw):
        raise ProviderError("timeout")

    monkeypatch.setattr(SandboxProvider, "create_transfer", down)
    p = (await api.post("/payouts", headers=auth(creator), json={"amount": 5000, "idempotency_key": "k-admin-retry-1"})).json()
    assert p["status"] == "pending"

    monkeypatch.undo()
    retried = await api.post(f"/admin/payouts/{p['id']}/retry", headers=auth(admin))
    assert retried.status_code == 200 and retried.json()["status"] == "succeeded"
    assert (await api.post(f"/admin/payouts/{p['id']}/retry", headers=auth(admin))).status_code == 409  # settled

    # A second one, this time the bank bounced it out of band.
    monkeypatch.setattr(SandboxProvider, "create_transfer", down)
    q = (await api.post("/payouts", headers=auth(creator), json={"amount": 5000, "idempotency_key": "k-admin-fail-1"})).json()
    assert q["status"] == "pending"
    monkeypatch.undo()
    failed = await api.post(f"/admin/payouts/{q['id']}/fail", headers=auth(admin), json={"reason": "Bank confirmed a bounce."})
    assert failed.status_code == 200 and failed.json()["status"] == "failed"
    # ₦12,000 earned, ₦5,000 paid by the retry; the bounced ₦5,000 is back, not lost.
    assert (await api.get("/earnings/summary", headers=auth(creator))).json()["payable"] == 7000
    assert (await api.post(f"/admin/payouts/{q['id']}/fail", headers=auth(admin), json={"reason": "again, again"})).status_code == 409
    assert (await api.post(f"/admin/payouts/{uuid.uuid4()}/retry", headers=auth(admin))).status_code == 404

    audit = (await api.get("/admin/audit?kind=admin.payout", headers=auth(admin))).json()
    assert {e["kind"] for e in audit} == {"admin.payout_retried", "admin.payout_failed"}
    assert all(e["actor_id"] == admin["user"]["id"] for e in audit)
    assert next(e for e in audit if e["kind"] == "admin.payout_failed")["data"]["reason"] == "Bank confirmed a bounce."


async def test_admin_funding_confirmation_needs_the_full_amount_and_is_audited(api, intel, monkeypatch):
    admin = await make_admin(api)
    _, org = await signup(api, "organisation")
    from integrations.payments.base import CollectionStatus

    async def not_yet(self, **kw):
        return CollectionStatus(received=False)

    monkeypatch.setattr(SandboxProvider, "check_collection", not_yet)
    c = (await api.post("/campaigns", headers=auth(org), json=campaign_body(pot=10000, expected_views=None, payout_rule={"rate_per_1000_views": 100}))).json()
    order = (await api.post(f"/campaigns/{c['id']}/funding", headers=auth(org), json={"method": "bank"})).json()
    await api.post(f"/campaigns/{c['id']}/funding/confirm", headers=auth(org))  # claimed, unconfirmed

    listed = (await api.get("/admin/funding?status_filter=awaiting_confirmation", headers=auth(admin))).json()
    assert [f["reference"] for f in listed] == [order["reference"]]

    short = await api.post(f"/admin/funding/{order['id']}/confirm", headers=auth(admin), json={"amount_received": 100, "note": "Saw ₦100 arrive."})
    assert short.status_code == 409
    assert (await api.get(f"/campaigns/{c['id']}", headers=auth(org))).json()["status"] == "pending_funding"

    ok = await api.post(f"/admin/funding/{order['id']}/confirm", headers=auth(admin), json={"amount_received": order["total"], "note": "Statement line 14 on 21 Sep."})
    assert ok.status_code == 200 and ok.json()["status"] == "confirmed"
    assert (await api.get(f"/campaigns/{c['id']}", headers=auth(org))).json()["status"] == "active"
    entry = next(e for e in (await api.get("/admin/audit?kind=admin.funding", headers=auth(admin))).json())
    assert entry["data"]["note"] == "Statement line 14 on 21 Sep." and entry["actor_id"] == admin["user"]["id"]
    assert (await api.post(f"/admin/funding/{order['id']}/confirm", headers=auth(admin), json={"amount_received": order["total"], "note": "duplicate attempt"})).status_code == 409


async def test_blocked_earnings_are_listed_for_review(api, intel):
    admin = await make_admin(api)
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org, expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0})
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    intel.trust[sid] = "flagged"
    await earn(api, intel, sid, 5000)
    blocked = (await api.get("/admin/earnings/blocked", headers=auth(admin))).json()
    assert [b["reason"] for b in blocked] == ["trust_flagged"] and blocked[0]["submission_id"] == sid and blocked[0]["accrued"] == 0
    assert (await api.get("/admin/overview", headers=auth(admin))).json()["blocked_earning_accounts"] == 1


async def test_admin_runs_a_settlement_and_a_sweep_on_demand(api, intel, monkeypatch):
    admin = await make_admin(api)
    from modules.earnings import jobs

    calls = []

    async def fake_settle(*a, **k):
        calls.append("settle")
        return 3

    async def fake_sweep(*a, **k):
        calls.append("sweep")
        return 1

    monkeypatch.setattr(jobs, "settle_tick", fake_settle)
    monkeypatch.setattr(jobs, "sweep_tick", fake_sweep)
    assert (await api.post("/admin/earnings/settle", headers=auth(admin))).json() == {"processed": 3}
    assert (await api.post("/admin/campaigns/sweep", headers=auth(admin))).json() == {"processed": 1}
    assert calls == ["settle", "sweep"]
    kinds = {e["kind"] for e in (await api.get("/admin/audit?kind=admin", headers=auth(admin))).json()}
    assert {"admin.settlement_run", "admin.sweep_run"} <= kinds


async def test_only_an_admin_can_verify_a_business_and_it_shows_on_the_brand(api, intel):
    admin = await make_admin(api)
    _, org = await signup(api, "organisation")
    _, other_org = await signup(api, "organisation")
    uid = org["user"]["id"]
    assert (await api.post(f"/admin/organisations/{uid}/verify-business", headers=auth(other_org), json={"verified": True})).status_code == 403
    r = await api.post(f"/admin/organisations/{uid}/verify-business", headers=auth(admin), json={"verified": True, "legal_name": "Gbedu Records Ltd."})
    assert r.status_code == 200 and r.json()["business_verified"] is True
    profile = (await api.get("/organisations/me/profile", headers=auth(org))).json()
    assert profile["business_verified"] is True and profile["business_legal_name"] == "Gbedu Records Ltd."
    campaign = await open_campaign(api, org)
    assert campaign["brand"]["verified"] is True
    creator = await make_creator(api)
    assert (await api.get(f"/campaigns/{campaign['id']}", headers=auth(creator))).json()["brand"]["verified"] is True
    assert (await api.post(f"/admin/organisations/{uuid.uuid4()}/verify-business", headers=auth(admin), json={"verified": True})).status_code == 404


async def test_audit_log_can_be_filtered(api, intel):
    admin = await make_admin(api)
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org)
    log = (await api.get(f"/admin/audit?campaign_id={campaign['id']}", headers=auth(admin))).json()
    kinds = [e["kind"] for e in log]
    assert "campaign.created" in kinds and "funding.confirmed" in kinds and "campaign.opened" in kinds
    assert all(e["campaign_id"] == campaign["id"] for e in log)
    only_funding = (await api.get(f"/admin/audit?campaign_id={campaign['id']}&kind=funding", headers=auth(admin))).json()
    assert {e["kind"] for e in only_funding} <= {"funding.order_created", "funding.confirmed"}
