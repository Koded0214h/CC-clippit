import asyncio
import json
import uuid

from core.config import get_settings
from integrations.payments.base import ProviderError, TransferRejected
from integrations.payments.sandbox import SandboxProvider, sign
from modules.wallet import service
from tests.http_app import api, auth, campaign_body, db_session, open_campaign, signup  # noqa: F401


async def verified_org_bank(client, org, number="0123456789", code="058", name="Guaranty Trust Bank") -> dict:
    r = await client.put("/organisations/me/bank-details", headers=auth(org), json={"bank_code": code, "bank_name": name, "account_number": number})
    r.raise_for_status()
    v = await client.post("/organisations/me/bank-details/verify", headers=auth(org))
    v.raise_for_status()
    return v.json()


async def funded_and_refunded(api, *, expected_views=1_000_000, rate=100):
    """A brand whose campaign was closed early and refunded — leaving money
    in the wallet's available balance."""
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org, expected_views=expected_views, payout_rule={"rate_per_1000_views": rate, "min_views_threshold": 0})
    closed = await api.post(f"/campaigns/{campaign['id']}/close", headers=auth(org))
    closed.raise_for_status()
    refund = await api.post(f"/campaigns/{campaign['id']}/refunds", headers=auth(org), json={"reason": "Ending early."})
    refund.raise_for_status()
    return org, campaign, refund.json()


async def _withdraw(api, org, amount, key=None):
    return await api.post("/wallet/withdraw", headers=auth(org), json={"amount": amount, "idempotency_key": key or f"key-{uuid.uuid4().hex}"})


async def _wallet(api, org):
    return (await api.get("/wallet", headers=auth(org))).json()


# --- brand bank details -----------------------------------------------------------------------------


async def test_setting_and_verifying_brand_bank_details(api):
    _, org = await signup(api, "organisation")
    assert (await api.get("/organisations/me/bank-details", headers=auth(org))).status_code == 404
    v = await verified_org_bank(api, org)
    assert v["verified"] is True and v["account_name"] == "SANDBOX ACCOUNT 6789"
    assert v["account_number_masked"] == "******6789"


async def test_a_creator_cannot_touch_brand_bank_details(api):
    _, creator = await signup(api, "creator")
    r = await api.put("/organisations/me/bank-details", headers=auth(creator), json={"bank_code": "058", "bank_name": "GTBank", "account_number": "0123456789"})
    assert r.status_code == 403


async def test_changing_bank_details_unverifies(api):
    _, org = await signup(api, "organisation")
    await verified_org_bank(api, org)
    await api.put("/organisations/me/bank-details", headers=auth(org), json={"bank_code": "011", "bank_name": "First Bank", "account_number": "9988776655"})
    assert (await api.get("/organisations/me/bank-details", headers=auth(org))).json()["verified"] is False


# --- wallet read -------------------------------------------------------------------------------------


async def test_a_refund_lands_in_the_brand_wallet_as_available(api):
    org, campaign, refund = await funded_and_refunded(api)
    assert refund["status"] == "succeeded" and refund["provider"] == "wallet"
    w = await _wallet(api, org)
    assert w["role"] == "organisation" and w["available"] == refund["amount"] and w["reserved"] == 0


async def test_a_creator_sees_the_creator_shaped_wallet(api):
    _, creator = await signup(api, "creator")
    w = await _wallet(api, creator)
    assert w["role"] == "creator" and w["held"] == 0 and w["available"] == 0


async def test_admins_have_no_wallet(api):
    from tests.http_app import make_admin

    admin = await make_admin(api)
    assert (await api.get("/wallet", headers=auth(admin))).status_code == 403


# --- withdrawing -------------------------------------------------------------------------------------


async def test_a_brand_withdrawal_reserves_sends_and_settles(api):
    org, campaign, refund = await funded_and_refunded(api)
    await verified_org_bank(api, org)
    amount = float(refund["amount"])
    r = await _withdraw(api, org, amount)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "succeeded" and body["amount"] == amount and body["fee"] == round(amount * 0.07, 2)
    assert body["reference"].startswith("CLW-")
    assert (await _wallet(api, org))["available"] == 0


async def test_you_cannot_withdraw_more_than_available(api):
    org, campaign, refund = await funded_and_refunded(api)
    await verified_org_bank(api, org)
    r = await _withdraw(api, org, float(refund["amount"]) + 1)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "insufficient_available"


async def test_the_minimum_withdrawal_is_enforced(api):
    org, campaign, refund = await funded_and_refunded(api)
    await verified_org_bank(api, org)
    assert (await _withdraw(api, org, 4999)).status_code == 422


async def test_an_unverified_bank_account_cannot_receive_money(api):
    org, campaign, refund = await funded_and_refunded(api)
    r = await _withdraw(api, org, float(refund["amount"]))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "bank_not_verified"


async def test_only_organisations_withdraw_from_the_wallet(api):
    _, creator = await signup(api, "creator")
    assert (await _withdraw(api, creator, 6000)).status_code == 403


async def test_a_repeated_request_key_is_one_withdrawal(api):
    org, campaign, refund = await funded_and_refunded(api)
    await verified_org_bank(api, org)
    first = (await _withdraw(api, org, 6000, key="confirm-1")).json()
    second = await _withdraw(api, org, 6000, key="confirm-1")
    assert second.status_code == 201 and second.json()["id"] == first["id"]
    listed = (await api.get("/wallet/withdrawals", headers=auth(org))).json()
    assert len(listed) == 1


async def test_reusing_a_key_for_a_different_amount_is_refused(api):
    org, campaign, refund = await funded_and_refunded(api)
    await verified_org_bank(api, org)
    await _withdraw(api, org, 6000, key="same-key")
    r = await _withdraw(api, org, 5000, key="same-key")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "idempotency_conflict"


async def test_two_simultaneous_withdrawals_cannot_spend_the_same_money(api):
    org, campaign, refund = await funded_and_refunded(api)  # ₦100,000 available
    await verified_org_bank(api, org)
    results = await asyncio.gather(_withdraw(api, org, 60_000), _withdraw(api, org, 60_000))
    codes = sorted(r.status_code for r in results)
    assert codes == [201, 409], [r.text for r in results]
    assert (await _wallet(api, org))["available"] == 40_000


# --- when the transfer doesn't go through -------------------------------------------------------------


async def test_a_rejected_transfer_returns_the_money_to_available(api, monkeypatch):
    org, campaign, refund = await funded_and_refunded(api)
    await verified_org_bank(api, org)

    async def reject(self, **kw):
        raise TransferRejected("The receiving bank rejected this account.")

    monkeypatch.setattr(SandboxProvider, "create_transfer", reject)
    body = (await _withdraw(api, org, 6000)).json()
    assert body["status"] == "failed"
    assert (await _wallet(api, org))["available"] == float(refund["amount"])
    inbox = (await api.get("/notifications", headers=auth(org))).json()["items"]
    assert any(n["title"] == "Withdrawal failed" for n in inbox)


async def test_an_unreachable_provider_leaves_the_withdrawal_pending_and_reserved(api, monkeypatch):
    org, campaign, refund = await funded_and_refunded(api)
    await verified_org_bank(api, org)

    async def down(self, **kw):
        raise ProviderError("timeout")

    monkeypatch.setattr(SandboxProvider, "create_transfer", down)
    body = (await _withdraw(api, org, 6000)).json()
    assert body["status"] == "pending"
    assert (await _wallet(api, org))["available"] == float(refund["amount"]) - 6000


async def test_reconciliation_sends_a_withdrawal_that_was_reserved_but_never_sent(api, monkeypatch):
    org, campaign, refund = await funded_and_refunded(api)
    await verified_org_bank(api, org)

    async def down(self, **kw):
        raise ProviderError("timeout")

    monkeypatch.setattr(SandboxProvider, "create_transfer", down)
    body = (await _withdraw(api, org, 6000)).json()
    monkeypatch.undo()

    async with db_session() as db:
        from datetime import timedelta

        moved = await service.reconcile(db, older_than=timedelta(seconds=-1))
    assert moved == 1
    assert (await api.get(f"/wallet/withdrawals/{body['id']}", headers=auth(org))).json()["status"] == "succeeded"


async def test_a_transfer_that_settles_later_completes_by_webhook(api):
    org, campaign, refund = await funded_and_refunded(api)
    await verified_org_bank(api, org, number="0123459999")  # the sandbox settles this one asynchronously

    body = (await _withdraw(api, org, 6000)).json()
    assert body["status"] == "processing"

    payload = json.dumps({"event": "transfer.success", "reference": body["reference"], "provider_reference": "SBX-1"}).encode()
    headers = {"X-Signature": sign(get_settings().payment_webhook_secret, payload)}
    r = await api.post("/webhooks/payments", content=payload, headers=headers)
    assert r.status_code == 200 and r.json()["handled"] is True
    assert (await api.get(f"/wallet/withdrawals/{body['id']}", headers=auth(org))).json()["status"] == "succeeded"


async def test_a_failed_transfer_webhook_releases_the_money(api):
    org, campaign, refund = await funded_and_refunded(api)
    await verified_org_bank(api, org, number="0123459999")
    body = (await _withdraw(api, org, 6000)).json()

    payload = json.dumps({"event": "transfer.failed", "reference": body["reference"], "failure_reason": "Account closed."}).encode()
    headers = {"X-Signature": sign(get_settings().payment_webhook_secret, payload)}
    assert (await api.post("/webhooks/payments", content=payload, headers=headers)).json()["handled"] is True
    got = (await api.get(f"/wallet/withdrawals/{body['id']}", headers=auth(org))).json()
    assert got["status"] == "failed"
    assert (await _wallet(api, org))["available"] == float(refund["amount"])


# --- visibility ----------------------------------------------------------------------------------------


async def test_a_withdrawal_is_visible_to_its_organisation_and_admin_only(api):
    org, campaign, refund = await funded_and_refunded(api)
    await verified_org_bank(api, org)
    body = (await _withdraw(api, org, 6000)).json()
    other = (await signup(api, "organisation"))[1]
    assert (await api.get(f"/wallet/withdrawals/{body['id']}", headers=auth(other))).status_code == 404
    assert (await api.get("/wallet/withdrawals", headers=auth(other))).json() == []
