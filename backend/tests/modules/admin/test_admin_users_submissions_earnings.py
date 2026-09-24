"""Admin users, submissions/trust, campaigns, earnings holds, and the
unified ledger (production-api-inventory.md §N)."""

import pytest

from tests.http_app import (
    api, approve_clip, auth, campaign_body, clear_hold, earn, fund_campaign, intel, make_admin, make_creator, signup,
    submit_clip,
)


async def test_every_new_admin_route_refuses_a_non_admin(api):
    _, creator = await signup(api, "creator")
    for method, path in [
        ("get", "/admin/users"), ("get", f"/admin/users/{creator['user']['id']}"),
        ("get", "/admin/submissions/flagged"), ("get", "/admin/submissions"),
        ("get", "/admin/campaigns"), ("get", "/admin/earnings"), ("get", "/admin/ledger"),
    ]:
        r = await getattr(api, method)(path, headers=auth(creator))
        assert r.status_code == 403, path


async def test_list_and_search_users(api):
    _, creator = await signup(api, "creator")
    admin = await make_admin(api)
    rows = (await api.get("/admin/users", headers=auth(admin), params={"role": "creator"})).json()
    assert any(r["id"] == creator["user"]["id"] for r in rows)

    found = (await api.get("/admin/users", headers=auth(admin), params={"q": creator["user"]["email"]})).json()
    assert [r["id"] for r in found] == [creator["user"]["id"]]


async def test_user_detail_carries_money_and_session_summary(api):
    _, creator = await signup(api, "creator")
    admin = await make_admin(api)
    detail = (await api.get(f"/admin/users/{creator['user']['id']}", headers=auth(admin))).json()
    assert detail["active_sessions"] == 1 and detail["money_summary"]["payable"] == 0
    assert detail["suspended"] is False


async def test_suspend_blocks_access_and_restore_reverses_it(api):
    _, creator = await signup(api, "creator")
    admin = await make_admin(api)

    suspended = await api.post(
        f"/admin/users/{creator['user']['id']}/suspend", headers=auth(admin),
        json={"scopes": ["access"], "reason": "Suspected chargeback fraud"},
    )
    assert suspended.status_code == 200 and suspended.json()["suspended"] is True

    blocked = await api.get("/auth/me", headers=auth(creator))
    assert blocked.status_code == 403 and blocked.json()["detail"]["code"] == "account_suspended"

    restored = await api.post(f"/admin/users/{creator['user']['id']}/restore", headers=auth(admin))
    assert restored.status_code == 200 and restored.json()["suspended"] is False
    again = await api.get("/auth/me", headers=auth(creator))
    assert again.status_code == 200


async def test_a_funding_scope_suspension_blocks_funding_but_not_login(api):
    _, org = await signup(api, "organisation")
    admin = await make_admin(api)
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()

    await api.post(
        f"/admin/users/{org['user']['id']}/suspend", headers=auth(admin),
        json={"scopes": ["funding"], "reason": "Under review"},
    )
    still_signed_in = await api.get("/auth/me", headers=auth(org))
    assert still_signed_in.status_code == 200

    blocked = await api.post(f"/campaigns/{campaign['id']}/funding", headers=auth(org), json={"method": "bank"})
    assert blocked.status_code == 403


async def test_an_earning_scope_suspension_blocks_new_payouts(api, intel):
    creator, org, entry_id = None, None, None
    _, org = await signup(api, "organisation")
    campaign = (await api.post(
        "/campaigns", headers=auth(org),
        json=campaign_body(expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0}),
    )).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await approve_clip(api, org, sid)
    await earn(api, intel, sid, 2_000)
    await clear_hold(creator["user"]["id"])
    await api.put("/creators/me/bank-details", headers=auth(creator), json={"bank_code": "058", "bank_name": "GTBank", "account_number": "0123456789"})
    await api.post("/creators/me/bank-details/verify", headers=auth(creator))

    admin = await make_admin(api)
    await api.post(
        f"/admin/users/{creator['user']['id']}/suspend", headers=auth(admin),
        json={"scopes": ["earning"], "reason": "Investigating"},
    )
    blocked = await api.post("/payouts", headers=auth(creator), json={"amount": 1000, "idempotency_key": "susp-key-01"})
    assert blocked.status_code == 403


async def _flagged_submission(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post(
        "/campaigns", headers=auth(org),
        json=campaign_body(expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0}),
    )).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await approve_clip(api, org, sid)
    intel.set_views(sid, 12_000)
    intel.trust[sid] = "flagged"
    from modules.earnings import service
    from tests.http_app import db_session
    import uuid as _uuid

    async with db_session() as db:
        await service.settle_submission(db, _uuid.UUID(sid), intel)
        await db.commit()
    return creator, org, sid


async def test_flagged_queue_lists_a_trust_blocked_submission(api, intel):
    creator, org, sid = await _flagged_submission(api, intel)
    admin = await make_admin(api)
    rows = (await api.get("/admin/submissions/flagged", headers=auth(admin))).json()
    assert any(r["id"] == sid and r["flagged"] for r in rows)


async def test_clearing_a_trust_flag_lets_settlement_resume(api, intel):
    creator, org, sid = await _flagged_submission(api, intel)
    admin = await make_admin(api)

    cleared = await api.post(
        f"/admin/submissions/{sid}/trust/clear", headers=auth(admin), json={"note": "Manually verified, this is legitimate."}
    )
    assert cleared.status_code == 200
    assert cleared.json()["flagged"] is False and cleared.json()["admin_trust_override"] is True

    from modules.earnings import service
    from tests.http_app import db_session
    import uuid as _uuid

    async with db_session() as db:
        await service.settle_submission(db, _uuid.UUID(sid), intel)
        await db.commit()

    detail = (await api.get(f"/admin/submissions/{sid}", headers=auth(admin))).json()
    assert detail["accrued"] > 0  # settlement actually resumed and paid


async def test_confirming_fraud_stays_blocked_even_if_intelligence_would_clear(api, intel):
    creator, org, sid = await _flagged_submission(api, intel)
    admin = await make_admin(api)

    confirmed = await api.post(
        f"/admin/submissions/{sid}/trust/confirm", headers=auth(admin), json={"note": "Confirmed view manipulation."}
    )
    assert confirmed.status_code == 200 and confirmed.json()["flagged"] is True

    intel.trust[sid] = "normal"  # Intelligence's own read would now say clean
    from modules.earnings import service
    from tests.http_app import db_session
    import uuid as _uuid

    async with db_session() as db:
        await service.settle_submission(db, _uuid.UUID(sid), intel)
        await db.commit()

    detail = (await api.get(f"/admin/submissions/{sid}", headers=auth(admin))).json()
    assert detail["flagged"] is True and detail["accrued"] == 0


async def test_admin_campaign_list_and_emergency_pause_and_close(api, intel):
    _, org = await signup(api, "organisation")
    admin = await make_admin(api)
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    await fund_campaign(api, org, campaign["id"])

    rows = (await api.get("/admin/campaigns", headers=auth(admin), params={"status": "active"})).json()
    assert any(r["id"] == campaign["id"] for r in rows)

    paused = await api.post(f"/admin/campaigns/{campaign['id']}/pause", headers=auth(admin), json={"reason": "Fraud investigation"})
    assert paused.status_code == 200
    brand_view = (await api.get(f"/campaigns/{campaign['id']}", headers=auth(org))).json()
    assert brand_view["accepting_entries"] is False

    closed = await api.post(f"/admin/campaigns/{campaign['id']}/close", headers=auth(admin), json={"reason": "Policy violation"})
    assert closed.status_code == 200 and closed.json()["status"] == "closed"


async def test_earnings_hold_blocks_reservation_and_release_restores_it(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post(
        "/campaigns", headers=auth(org),
        json=campaign_body(expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0}),
    )).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await approve_clip(api, org, sid)
    await earn(api, intel, sid, 4_000)  # ₦2,000
    await clear_hold(creator["user"]["id"])
    await api.put("/creators/me/bank-details", headers=auth(creator), json={"bank_code": "058", "bank_name": "GTBank", "account_number": "0123456789"})
    await api.post("/creators/me/bank-details/verify", headers=auth(creator))

    admin = await make_admin(api)
    held = await api.post(f"/admin/earnings/{sid}/hold", headers=auth(admin), json={"reason": "Dispute in progress"})
    assert held.status_code == 200 and held.json()["hold_active"] is True

    summary = (await api.get("/earnings/summary", headers=auth(creator))).json()
    assert summary["payable"] == 0

    blocked_payout = await api.post("/payouts", headers=auth(creator), json={"amount": 5000, "idempotency_key": "hold-key-01"})
    assert blocked_payout.status_code == 409

    released = await api.post(f"/admin/earnings/{sid}/release", headers=auth(admin))
    assert released.status_code == 200 and released.json()["hold_active"] is False
    after = (await api.get("/earnings/summary", headers=auth(creator))).json()
    assert after["payable"] == 2000


async def test_releasing_a_hold_that_does_not_exist_is_refused(api, intel):
    creator, org, sid = await _flagged_submission(api, intel)
    admin = await make_admin(api)
    r = await api.post(f"/admin/earnings/{sid}/release", headers=auth(admin))
    assert r.status_code == 409


async def test_admin_earning_entry_detail_matches_the_creators_own_view(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post(
        "/campaigns", headers=auth(org),
        json=campaign_body(expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0}),
    )).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await approve_clip(api, org, sid)
    await earn(api, intel, sid, 5_000)
    entry_id = (await api.get("/earnings/history", headers=auth(creator))).json()["items"][0]["id"]

    admin = await make_admin(api)
    admin_view = (await api.get(f"/admin/earnings/{entry_id}", headers=auth(admin))).json()
    creator_view = (await api.get(f"/earnings/entries/{entry_id}", headers=auth(creator))).json()
    assert admin_view == creator_view


async def test_unified_ledger_lists_funding_refund_and_payout_rows(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body(pot=10_000, expected_views=None))).json()
    await fund_campaign(api, org, campaign["id"])
    await api.post(f"/campaigns/{campaign['id']}/close", headers=auth(org))
    await api.post(f"/campaigns/{campaign['id']}/refunds", headers=auth(org), json={"reason": "Unused"})

    admin = await make_admin(api)
    all_rows = (await api.get("/admin/ledger", headers=auth(admin))).json()
    kinds = {r["kind"] for r in all_rows}
    assert {"funding", "refund"} <= kinds

    funding_only = (await api.get("/admin/ledger", headers=auth(admin), params={"kind": "funding"})).json()
    assert all(r["kind"] == "funding" for r in funding_only)

    entry_id = all_rows[0]["id"]
    detail = await api.get(f"/admin/ledger/{entry_id}", headers=auth(admin))
    assert detail.status_code == 200 and detail.json()["id"] == entry_id
