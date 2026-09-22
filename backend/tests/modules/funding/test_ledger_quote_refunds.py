"""Funding quotes, the brand's own transaction ledger, refunds, and public
receipt verification (production-api-inventory.md §J). Only the parts
that don't need a real payment-provider account or a tax/legal decision —
see the code comments for what's still open."""

import pytest

from tests.http_app import api, auth, campaign_body, fund_campaign, intel, signup


async def test_funding_quote_matches_what_the_order_actually_charges(api):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body(pot=100_000, expected_views=None))).json()

    quote = (await api.post(f"/campaigns/{campaign['id']}/funding/quote", headers=auth(org))).json()
    assert quote["pot"] == 100_000 and quote["fee"] == 1500 and quote["total"] == 101_500
    assert "bank" in quote["methods"] and "card" in quote["methods"]

    order = (await api.post(f"/campaigns/{campaign['id']}/funding", headers=auth(org), json={"method": "bank"})).json()
    assert order["total"] == quote["total"]


async def test_the_quote_does_not_lock_terms_or_create_an_order(api):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    await api.post(f"/campaigns/{campaign['id']}/funding/quote", headers=auth(org))
    still_draft = await api.get(f"/campaigns/{campaign['id']}", headers=auth(org))
    assert still_draft.json()["status"] == "draft"


async def test_the_brand_ledger_lists_a_funded_campaigns_order(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body(pot=50_000, expected_views=None))).json()
    await fund_campaign(api, org, campaign["id"])

    ledger = (await api.get("/organisations/me/transactions", headers=auth(org))).json()
    assert ledger["total"] == 1
    row = ledger["items"][0]
    assert row["kind"] == "funding" and row["campaign_id"] == campaign["id"] and row["status"] == "confirmed"
    assert row["amount"] == 50_750 and row["fee"] == 750

    detail = await api.get(f"/organisations/me/transactions/{row['id']}", headers=auth(org))
    assert detail.status_code == 200 and detail.json() == row


async def test_one_organisation_cannot_see_anothers_ledger_entry(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    await fund_campaign(api, org, campaign["id"])
    tx_id = (await api.get("/organisations/me/transactions", headers=auth(org))).json()["items"][0]["id"]

    _, other = await signup(api, "organisation")
    r = await api.get(f"/organisations/me/transactions/{tx_id}", headers=auth(other))
    assert r.status_code == 404


async def test_a_refund_needs_a_closed_campaign(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body(pot=20_000, expected_views=None))).json()
    await fund_campaign(api, org, campaign["id"])
    still_active = await api.post(f"/campaigns/{campaign['id']}/refunds", headers=auth(org), json={"reason": "Ended early"})
    assert still_active.status_code == 409


async def test_closing_an_unspent_campaign_refunds_the_whole_pot_minus_nothing_owed(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body(pot=20_000, expected_views=None))).json()
    await fund_campaign(api, org, campaign["id"])
    await api.post(f"/campaigns/{campaign['id']}/close", headers=auth(org))

    refund = await api.post(f"/campaigns/{campaign['id']}/refunds", headers=auth(org), json={"reason": "No clips came in"})
    assert refund.status_code == 201
    body = refund.json()
    assert body["amount"] == 20_000 and body["status"] == "succeeded" and body["sandbox"] is True

    listed = (await api.get(f"/campaigns/{campaign['id']}/refunds", headers=auth(org))).json()
    assert len(listed) == 1 and listed[0]["id"] == body["id"]

    ledger = (await api.get("/organisations/me/transactions", headers=auth(org), params={"kind": "refund"})).json()
    assert ledger["total"] == 1
    assert ledger["items"][0]["kind"] == "refund" and ledger["items"][0]["amount"] == 20_000


async def test_requesting_a_second_refund_returns_the_same_one(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body(pot=20_000, expected_views=None))).json()
    await fund_campaign(api, org, campaign["id"])
    await api.post(f"/campaigns/{campaign['id']}/close", headers=auth(org))

    first = (await api.post(f"/campaigns/{campaign['id']}/refunds", headers=auth(org), json={"reason": "x"})).json()
    second = (await api.post(f"/campaigns/{campaign['id']}/refunds", headers=auth(org), json={"reason": "y"})).json()
    assert first["id"] == second["id"]


async def test_a_fully_spent_campaign_has_nothing_to_refund(api, intel):
    from tests.http_app import approve_clip, earn, make_creator, submit_clip

    _, org = await signup(api, "organisation")
    campaign = (await api.post(
        "/campaigns", headers=auth(org),
        json=campaign_body(pot=6000, expected_views=None, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0}),
    )).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await approve_clip(api, org, sid)
    await earn(api, intel, sid, 12_000)  # exactly exhausts the ₦6,000 pot
    await api.post(f"/campaigns/{campaign['id']}/close", headers=auth(org))

    refund = await api.post(f"/campaigns/{campaign['id']}/refunds", headers=auth(org), json={"reason": "x"})
    assert refund.status_code == 409


async def test_receipt_verification_finds_a_funding_order_by_reference(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    funded = await fund_campaign(api, org, campaign["id"])

    r = await api.get(f"/receipts/{funded['reference']}/verify")
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "funding" and body["status"] == "confirmed" and body["amount"] == funded["total"]
    assert len(body["digest"]) == 32


async def test_receipt_verification_is_public_and_safe_for_an_unknown_reference(api):
    r = await api.get("/receipts/not-a-real-reference/verify")
    assert r.status_code == 404
