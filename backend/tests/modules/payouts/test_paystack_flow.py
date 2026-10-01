"""Funding and withdrawing through the real app with Paystack as the provider
(Paystack itself scripted). The interesting part is the seams: our references
going out in Paystack's format and coming back from webhooks, and amounts
crossing the kobo boundary."""

import hashlib
import hmac
import json

import httpx
import pytest

from core.config import get_settings
from integrations import payments
from integrations.payments import paystack as paystack_module
from tests.http_app import (  # noqa: F401
    api, approve_clip, auth, campaign_body, clear_hold, db_session, earn, intel, make_creator, open_campaign, signup, submit_clip,
)
from tests.integrations.payments.test_paystack import KEY, FakePaystack

BASE = "https://api.paystack.test"


@pytest.fixture
def ps(monkeypatch):
    fake = FakePaystack()
    fake.on("POST", "/transaction/initialize", {"status": True, "data": {"authorization_url": "https://checkout.paystack.test/x", "access_code": "AC_9"}})
    fake.on("POST", "/transferrecipient", {"status": True, "data": {"recipient_code": "RCP_1"}})
    fake.on("GET", "/bank/resolve", {"status": True, "data": {"account_name": "TOBI ADEYEMI", "account_number": "0123456789"}})

    real = paystack_module.PaystackProvider
    monkeypatch.setattr(paystack_module, "PaystackProvider", lambda key, base: real(key, BASE, transport=fake.transport()))
    settings = get_settings()
    monkeypatch.setattr(settings, "payment_provider", "paystack")
    monkeypatch.setattr(settings, "paystack_secret_key", KEY)
    payments.get_provider.cache_clear()
    yield fake
    payments.get_provider.cache_clear()


def _webhook(payload: dict) -> tuple[bytes, dict]:
    body = json.dumps(payload).encode()
    return body, {"x-paystack-signature": hmac.new(KEY.encode(), body, hashlib.sha512).hexdigest()}


async def test_funding_sends_the_brand_to_a_hosted_checkout_and_a_signed_charge_opens_the_campaign(api, intel, ps):
    _, org = await signup(api, "organisation")
    c = (await api.post("/campaigns", headers=auth(org), json=campaign_body(pot=500000, expected_views=None, payout_rule={"rate_per_1000_views": 500}))).json()
    order = (await api.post(f"/campaigns/{c['id']}/funding", headers=auth(org), json={"method": "bank"})).json()

    assert order["provider"] == "paystack" and order["sandbox"] is False
    assert order["checkout_url"] == "https://checkout.paystack.test/x" and order["collection"] is None
    assert order["total"] == 575_000
    sent = ps.sent("POST", "/transaction/initialize")[0][2]
    assert sent["amount"] == 57_500_000 and sent["email"] == org["user"]["email"]
    assert sent["reference"] == "clippit-" + order["reference"].lower()
    # Set explicitly, not left to whatever's configured in the Paystack
    # dashboard — that drifted stale across the last infra move and sent
    # brands to a dead page right after paying.
    assert sent["callback_url"] == f"{get_settings().app_url}/brand/campaigns/new/funded"

    # Not paid yet: the brand's claim opens nothing.
    unpaid = await api.post(f"/campaigns/{c['id']}/funding/confirm", headers=auth(org))
    assert unpaid.json()["status"] == "awaiting_confirmation"

    body, headers = _webhook({"event": "charge.success", "data": {"reference": sent["reference"], "amount": 57_500_000, "id": 77}})
    r = await api.post("/webhooks/payments", content=body, headers=headers)
    assert r.status_code == 200 and r.json() == {"received": True, "handled": True, "first_time": True}
    assert (await api.get(f"/campaigns/{c['id']}", headers=auth(org))).json()["status"] == "active"
    again = await api.post("/webhooks/payments", content=body, headers=headers)
    assert again.json()["first_time"] is False


async def test_confirm_button_verifies_with_paystack_and_opens_when_paid(api, intel, ps):
    _, org = await signup(api, "organisation")
    c = (await api.post("/campaigns", headers=auth(org), json=campaign_body(pot=1000, expected_views=None, payout_rule={"rate_per_1000_views": 100}))).json()
    order = (await api.post(f"/campaigns/{c['id']}/funding", headers=auth(org), json={"method": "card"})).json()
    assert ps.sent("POST", "/transaction/initialize")[0][2]["channels"] == ["card"]
    ps.on("GET", "/transaction/verify/clippit-" + order["reference"].lower(), {"status": True, "data": {"status": "success", "amount": 115_000}})
    done = (await api.post(f"/campaigns/{c['id']}/funding/confirm", headers=auth(org))).json()
    assert done["status"] == "confirmed" and done["campaign_status"] == "active"


async def test_a_short_payment_from_paystack_does_not_open_the_campaign(api, intel, ps):
    _, org = await signup(api, "organisation")
    c = (await api.post("/campaigns", headers=auth(org), json=campaign_body(pot=1000, expected_views=None, payout_rule={"rate_per_1000_views": 100}))).json()
    order = (await api.post(f"/campaigns/{c['id']}/funding", headers=auth(org), json={"method": "bank"})).json()
    body, headers = _webhook({"event": "charge.success", "data": {"reference": "clippit-" + order["reference"].lower(), "amount": 50_000, "id": 1}})
    await api.post("/webhooks/payments", content=body, headers=headers)
    assert (await api.get(f"/campaigns/{c['id']}", headers=auth(org))).json()["status"] == "pending_funding"


async def test_a_forged_paystack_webhook_is_refused(api, intel, ps):
    body = json.dumps({"event": "charge.success", "data": {"reference": "clippit-clp-2609-4f1a", "amount": 1}}).encode()
    bad = {"x-paystack-signature": hmac.new(b"sk_test_wrong", body, hashlib.sha512).hexdigest()}
    assert (await api.post("/webhooks/payments", content=body, headers=bad)).status_code == 401
    assert (await api.post("/webhooks/payments", content=body)).status_code == 401


async def test_the_bank_list_and_account_name_come_from_paystack(api, intel, ps):
    ps.on("GET", "/bank", {"status": True, "data": [{"name": "Guaranty Trust Bank", "code": "058", "active": True}], "meta": {"next": None}})
    creator = await make_creator(api)
    banks = (await api.get("/banks", headers=auth(creator))).json()
    assert banks == [{"code": "058", "name": "Guaranty Trust Bank"}]
    r = await api.post("/banks/resolve", headers=auth(creator), json={"bank_code": "058", "account_number": "0123456789"})
    assert r.json()["account_name"] == "TOBI ADEYEMI"


async def _earner(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body(expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0}))).json()
    order = (await api.post(f"/campaigns/{campaign['id']}/funding", headers=auth(org), json={"method": "bank"})).json()
    body, headers = _webhook({"event": "charge.success", "data": {"reference": "clippit-" + order["reference"].lower(), "amount": int(order["total"] * 100), "id": 5}})
    await api.post("/webhooks/payments", content=body, headers=headers)
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await approve_clip(api, org, sid)
    await earn(api, intel, sid, 12_000)  # ₦6,000
    await clear_hold(creator["user"]["id"])
    await api.put("/creators/me/bank-details", headers=auth(creator), json={"bank_code": "058", "bank_name": "GTBank", "account_number": "0123456789"})
    assert (await api.post("/creators/me/bank-details/verify", headers=auth(creator))).json()["account_name"] == "TOBI ADEYEMI"
    return creator


async def test_a_withdrawal_goes_to_paystack_in_kobo_and_settles_by_webhook(api, intel, ps):
    creator = await _earner(api, intel)
    ps.on("POST", "/transfer", {"status": True, "data": {"status": "pending", "transfer_code": "TRF_5"}})
    p = (await api.post("/payouts", headers=auth(creator), json={"amount": 5000, "idempotency_key": "ps-key-0001"})).json()
    assert p["status"] == "processing" and p["sandbox"] is False and p["provider"] == "paystack"

    sent = ps.sent("POST", "/transfer")[0][2]
    # 5,000 gross, 7% withdrawal fee: Paystack is sent the net, in kobo.
    assert sent["amount"] == 465_000 and sent["reference"] == "clippit-" + p["reference"].lower()
    assert sent["recipient"] == "RCP_1"
    assert ps.sent("POST", "/transferrecipient")[0][2]["name"] == "TOBI ADEYEMI"  # the verified name, not what the creator typed

    body, headers = _webhook({"event": "transfer.success", "data": {"reference": sent["reference"], "transfer_code": "TRF_5"}})
    assert (await api.post("/webhooks/payments", content=body, headers=headers)).json()["handled"] is True
    assert (await api.get(f"/payouts/{p['id']}", headers=auth(creator))).json()["status"] == "succeeded"
    assert (await api.get("/earnings/summary", headers=auth(creator))).json()["paid_all_time"] == 5000


async def test_a_reversal_webhook_releases_a_pending_payout_but_only_flags_a_settled_one(api, intel, ps):
    creator = await _earner(api, intel)
    ps.on("POST", "/transfer", {"status": True, "data": {"status": "pending", "transfer_code": "TRF_6"}})
    pending = (await api.post("/payouts", headers=auth(creator), json={"amount": 5000, "idempotency_key": "ps-key-0002"})).json()
    ref = "clippit-" + pending["reference"].lower()
    body, headers = _webhook({"event": "transfer.reversed", "data": {"reference": ref, "transfer_code": "TRF_6", "reason": "Account closed"}})
    await api.post("/webhooks/payments", content=body, headers=headers)
    got = (await api.get(f"/payouts/{pending['id']}", headers=auth(creator))).json()
    assert got["status"] == "failed" and got["failure_reason"] == "Account closed"
    assert (await api.get("/earnings/summary", headers=auth(creator))).json()["payable"] == 6000  # released

    ps.on("POST", "/transfer", {"status": True, "data": {"status": "success", "transfer_code": "TRF_7"}})
    done = (await api.post("/payouts", headers=auth(creator), json={"amount": 5000, "idempotency_key": "ps-key-0003"})).json()
    assert done["status"] == "succeeded"
    body, headers = _webhook({"event": "transfer.reversed", "data": {"reference": "clippit-" + done["reference"].lower(), "reason": "Bank reversal"}})
    await api.post("/webhooks/payments", content=body, headers=headers)
    assert (await api.get(f"/payouts/{done['id']}", headers=auth(creator))).json()["status"] == "succeeded"  # not auto-undone

    from sqlalchemy import select

    from modules.audit.models import AuditEvent

    async with db_session() as db:
        kinds = [e.kind for e in await db.scalars(select(AuditEvent).where(AuditEvent.kind == "payout.reversed_after_success"))]
    assert kinds == ["payout.reversed_after_success"]  # an admin can see it


async def test_paystack_needing_balance_leaves_the_payout_pending_not_failed(api, intel, ps):
    creator = await _earner(api, intel)
    ps.on("POST", "/transfer", httpx.Response(400, json={"status": False, "message": "Your balance is not enough to fulfil this request"}))
    p = (await api.post("/payouts", headers=auth(creator), json={"amount": 5000, "idempotency_key": "ps-key-0004"})).json()
    assert p["status"] == "pending"
    assert (await api.get("/earnings/summary", headers=auth(creator))).json()["processing"] == 5000  # still reserved


def test_production_needs_a_live_paystack_key(monkeypatch):
    from core.startup import check

    s = get_settings()
    monkeypatch.setattr(s, "environment", "production")
    monkeypatch.setattr(s, "payment_provider", "paystack")
    monkeypatch.setattr(s, "paystack_secret_key", "sk_test_x")
    monkeypatch.setattr(s, "jwt_secret", "a" * 40)
    monkeypatch.setattr(s, "internal_service_secret", "b" * 40)
    monkeypatch.setattr(s, "email_backend", "smtp")
    assert any("live key" in p for p in check(s))
    monkeypatch.setattr(s, "paystack_secret_key", "sk_live_x")
    assert check(s) == []  # Paystack signs with its own key: no separate webhook secret to set


def test_paystack_without_a_key_refuses_to_build(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "payment_provider", "paystack")
    monkeypatch.setattr(s, "paystack_secret_key", "")
    payments.get_provider.cache_clear()
    with pytest.raises(RuntimeError, match="PAYSTACK_SECRET_KEY"):
        payments.get_provider()
    payments.get_provider.cache_clear()
