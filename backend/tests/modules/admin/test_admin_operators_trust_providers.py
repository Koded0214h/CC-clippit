"""Operator invitations/permissions, trust rules proxy, random audits, and
provider health (production-api-inventory.md §O)."""

import pytest

from tests.http_app import api, auth, intel, make_admin, signup


async def test_a_fresh_admin_has_full_legacy_permissions(api):
    admin = await make_admin(api)
    r = await api.get("/auth/permissions", headers=auth(admin))
    assert r.status_code == 200 and r.json()["permissions"] == ["*"]


async def test_a_non_admin_has_no_permissions_entry(api):
    _, creator = await signup(api, "creator")
    r = (await api.get("/auth/permissions", headers=auth(creator))).json()
    assert r["permissions"] == []


async def test_inviting_and_accepting_an_operator(api):
    admin = await make_admin(api)
    invited = await api.post(
        "/admin/operators/invitations", headers=auth(admin),
        json={"email": "newop@example.com", "permissions": ["view_disputes"]},
    )
    assert invited.status_code == 201
    body = invited.json()
    token = body["invite_token"]

    status_before = (await api.get(f"/auth/admin-invitations/{token}")).json()
    assert status_before == {"status": "valid", "email": "newop@example.com", "permissions": ["view_disputes"]}

    accepted = await api.post(
        f"/auth/admin-invitations/{token}/accept", json={"full_name": "New Operator", "password": "OperatorPass123"}
    )
    assert accepted.status_code == 201
    assert accepted.json()["user"]["role"] == "admin"

    used = (await api.get(f"/auth/admin-invitations/{token}")).json()
    assert used["status"] == "used"

    replay = await api.post(
        f"/auth/admin-invitations/{token}/accept", json={"full_name": "Again", "password": "OperatorPass123"}
    )
    assert replay.status_code == 400


async def test_an_unknown_invitation_token_is_invalid_not_a_500(api):
    r = await api.get("/auth/admin-invitations/not-a-real-token")
    assert r.json()["status"] == "invalid"


async def test_operators_are_listed_with_permissions_and_last_active(api):
    admin = await make_admin(api)
    rows = (await api.get("/admin/operators", headers=auth(admin))).json()
    assert any(r["id"] == admin["user"]["id"] for r in rows)


async def test_an_operator_cannot_change_their_own_permissions(api):
    admin = await make_admin(api)
    r = await api.patch(f"/admin/operators/{admin['user']['id']}", headers=auth(admin), json={"permissions": ["*"]})
    assert r.status_code == 403


async def test_admin_can_change_another_operators_permissions(api):
    admin = await make_admin(api)
    other = await make_admin(api)
    r = await api.patch(f"/admin/operators/{other['user']['id']}", headers=auth(admin), json={"permissions": ["view_ledger"]})
    assert r.status_code == 200 and r.json()["permissions"] == ["view_ledger"]


async def test_suspending_an_operator_signs_them_out_and_restore_reverses_it(api):
    admin = await make_admin(api)
    other = await make_admin(api)

    suspended = await api.post(f"/admin/operators/{other['user']['id']}/suspend", headers=auth(admin))
    assert suspended.status_code == 200 and suspended.json()["suspended"] is True
    # Suspending an operator revokes every session immediately, so this
    # 401s on the dead session before it would ever reach the (also
    # correct) 403 "account_suspended" check a still-live token would hit.
    blocked = await api.get("/auth/me", headers=auth(other))
    assert blocked.status_code == 401

    restored = await api.post(f"/admin/operators/{other['user']['id']}/restore", headers=auth(admin))
    assert restored.status_code == 200 and restored.json()["suspended"] is False


async def test_an_operator_cannot_suspend_themselves(api):
    admin = await make_admin(api)
    r = await api.post(f"/admin/operators/{admin['user']['id']}/suspend", headers=auth(admin))
    assert r.status_code == 403


async def test_trust_rules_proxies_intelligence(api, intel):
    admin = await make_admin(api)
    r = await api.get("/admin/trust/rules", headers=auth(admin))
    assert r.status_code == 200


async def test_random_audits_lists_unflagged_submissions(api, intel):
    from tests.http_app import approve_clip, campaign_body, fund_campaign, make_creator, submit_clip

    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await approve_clip(api, org, sid)

    admin = await make_admin(api)
    rows = (await api.get("/admin/submissions/random-audits", headers=auth(admin))).json()
    assert any(r["submission_id"] == sid for r in rows)


async def test_generic_trust_review_is_recorded(api, intel):
    from tests.http_app import approve_clip, campaign_body, fund_campaign, make_creator, submit_clip

    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await approve_clip(api, org, sid)

    admin = await make_admin(api)
    r = await api.post(
        f"/admin/submissions/{sid}/trust/review", headers=auth(admin),
        json={"outcome": "legitimate", "source": "random_audit", "notes": "Checked manually, looks fine."},
    )
    assert r.status_code == 201


async def test_provider_health_reports_sandbox_payment_provider(api):
    admin = await make_admin(api)
    rows = (await api.get("/admin/providers", headers=auth(admin))).json()
    payment = next(r for r in rows if r["kind"] == "payment")
    assert payment["configured"] is True and payment["sandbox"] is True


async def test_operator_routes_refuse_a_non_admin(api):
    _, creator = await signup(api, "creator")
    for method, path, kwargs in [
        ("get", "/admin/operators", {}),
        ("post", "/admin/operators/invitations", {"json": {"email": "x@example.com"}}),
        ("get", "/admin/trust/rules", {}),
        ("get", "/admin/submissions/random-audits", {}),
        ("get", "/admin/providers", {}),
    ]:
        r = await getattr(api, method)(path, headers=auth(creator), **kwargs)
        assert r.status_code == 403, path
