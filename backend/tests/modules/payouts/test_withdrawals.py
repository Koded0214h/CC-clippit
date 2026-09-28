import asyncio
import json
import uuid
from decimal import Decimal

from sqlalchemy import select

from core.config import get_settings
from integrations.payments.base import ProviderError, TransferRejected, TransferResult, TransferStatus
from integrations.payments.sandbox import SandboxProvider, sign
from modules.payouts import models as payout_models
from modules.payouts import service
from tests.http_app import (  # noqa: F401
    api, auth, clear_hold, db_session, earn, intel, make_creator, open_campaign, signup, submit_clip, verified_bank,
)


async def _earner(api, intel, views=12_400, **campaign_kw):
    """A creator with a verified bank account and `views` worth of *payable*
    earnings at ₦500 per thousand (12,400 views → ₦6,000)."""
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(
        api, org, expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 1000}, **campaign_kw
    )
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"], title="Hunger interrupted")).json()["id"]
    await earn(api, intel, sid, views)
    await clear_hold(creator["user"]["id"])
    await verified_bank(api, creator)
    return org, creator, sid


async def _withdraw(api, creator, amount, key=None):
    return await api.post(
        "/payouts", headers=auth(creator), json={"amount": amount, "idempotency_key": key or f"key-{uuid.uuid4().hex}"}
    )


async def _balance(api, creator):
    return (await api.get("/earnings/summary", headers=auth(creator))).json()


# --- bank verification ------------------------------------------------------------------------------


async def test_resolving_an_account_shows_the_name_before_saving(api, intel):
    creator = await make_creator(api)
    r = await api.post("/banks/resolve", headers=auth(creator), json={"bank_code": "058", "account_number": "0123456789"})
    assert r.status_code == 200
    assert r.json() == {"account_name": "SANDBOX ACCOUNT 6789", "bank_code": "058", "account_number_masked": "******6789"}
    bad = await api.post("/banks/resolve", headers=auth(creator), json={"bank_code": "058", "account_number": "0123450000"})
    assert bad.status_code == 422 and "couldn't find" in bad.json()["detail"]
    assert (await api.post("/banks/resolve", headers=auth(creator), json={"bank_code": "058", "account_number": "123"})).status_code == 422


async def test_verifying_bank_details_stores_the_account_name(api, intel):
    creator = await make_creator(api)
    await api.put("/creators/me/bank-details", headers=auth(creator), json={"bank_code": "058", "bank_name": "GTBank", "account_number": "0123456789"})
    v = (await api.post("/creators/me/bank-details/verify", headers=auth(creator))).json()
    assert v["verified"] is True and v["account_name"] == "SANDBOX ACCOUNT 6789" and v["verified_at"]


async def test_a_bad_account_stays_unverified(api, intel):
    creator = await make_creator(api)
    await api.put("/creators/me/bank-details", headers=auth(creator), json={"bank_code": "058", "bank_name": "GTBank", "account_number": "0123450000"})
    assert (await api.post("/creators/me/bank-details/verify", headers=auth(creator))).status_code == 422
    assert (await api.get("/creators/me/bank-details", headers=auth(creator))).json()["verified"] is False


async def test_verifying_with_nothing_saved_is_a_404_and_changing_details_unverifies(api, intel):
    creator = await make_creator(api)
    assert (await api.post("/creators/me/bank-details/verify", headers=auth(creator))).status_code == 404
    await verified_bank(api, creator)
    await api.put("/creators/me/bank-details", headers=auth(creator), json={"bank_code": "011", "bank_name": "First Bank", "account_number": "9988776655"})
    assert (await api.get("/creators/me/bank-details", headers=auth(creator))).json()["verified"] is False


# --- withdrawing ------------------------------------------------------------------------------------------------


async def test_a_withdrawal_reserves_sends_and_settles(api, intel):
    org, creator, _ = await _earner(api, intel)
    r = await _withdraw(api, creator, 6000)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["status"] == "succeeded" and p["amount"] == 6000 and p["fee"] == 420 and p["net"] == 5580
    assert p["reference"].startswith("CLP-") and p["sandbox"] is True
    assert p["destination"] == {"bank_code": "058", "bank_name": "Guaranty Trust Bank", "account_number_masked": "******6789", "account_name": "SANDBOX ACCOUNT 6789"}
    assert p["completed_at"] and p["creator_name"] == "Test creator"

    b = await _balance(api, creator)
    assert b["payable"] == 0 and b["paid_all_time"] == 6000 and b["completed_payouts"] == 1 and b["processing"] == 0


async def test_the_receipt_says_where_the_money_came_from(api, intel):
    _, creator, _ = await _earner(api, intel, title="Indomie run")
    p = (await _withdraw(api, creator, 6000)).json()
    receipt = (await api.get(f"/payouts/{p['id']}", headers=auth(creator))).json()
    prov = receipt["provenance"]
    assert prov["approved_clips"] == 1 and prov["campaigns"] == ["Indomie run"] and prov["billable_views"] == 12_000
    assert prov["sources"] == [{"campaign_title": "Indomie run", "clip": "Hunger interrupted", "amount": 6000}]


async def test_a_partial_withdrawal_leaves_the_rest_payable(api, intel):
    _, creator, _ = await _earner(api, intel, views=20_000)  # ₦10,000 payable
    assert (await _withdraw(api, creator, 5000)).json()["status"] == "succeeded"
    b = await _balance(api, creator)
    assert b["payable"] == 5000 and b["paid_all_time"] == 5000
    assert (await _withdraw(api, creator, 5000)).status_code == 201
    assert (await _balance(api, creator))["payable"] == 0


async def test_you_cannot_withdraw_more_than_is_payable(api, intel):
    _, creator, _ = await _earner(api, intel)
    r = await _withdraw(api, creator, 6000.01)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "insufficient_payable"
    assert (await _balance(api, creator))["payable"] == 6000  # nothing was reserved


async def test_earnings_still_in_the_hold_cannot_be_withdrawn(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org, expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0})
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await earn(api, intel, sid, 12_000)  # ₦6,000, still in the hold
    await verified_bank(api, creator)
    r = await _withdraw(api, creator, 6000)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "insufficient_payable"


async def test_the_minimum_withdrawal_is_enforced(api, intel):
    _, creator, _ = await _earner(api, intel)
    r = await _withdraw(api, creator, 999)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "below_minimum"
    assert (await _withdraw(api, creator, 0)).status_code == 422


async def test_an_unverified_bank_account_cannot_receive_money(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org, expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0})
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await earn(api, intel, sid, 12_000)  # ₦6,000
    await clear_hold(creator["user"]["id"])
    r = await _withdraw(api, creator, 6000)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "bank_not_verified"
    await api.put("/creators/me/bank-details", headers=auth(creator), json={"bank_code": "058", "bank_name": "GTBank", "account_number": "0123456789"})
    assert (await _withdraw(api, creator, 6000)).json()["detail"]["code"] == "bank_not_verified"  # saved, not verified


async def test_only_creators_withdraw_and_only_verified_ones(api, intel):
    _, org = await signup(api, "organisation")
    assert (await _withdraw(api, org, 1000)).status_code == 403
    unverified = (await signup(api, "creator", verify=False))[1]
    r = await _withdraw(api, unverified, 1000)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "email_not_verified"


# --- idempotency and double spends ---------------------------------------------------------------------------------


async def test_a_repeated_request_key_is_one_payout(api, intel):
    _, creator, _ = await _earner(api, intel)
    first = (await _withdraw(api, creator, 6000, key="confirm-screen-1")).json()
    second = await _withdraw(api, creator, 6000, key="confirm-screen-1")
    assert second.status_code == 201 and second.json()["id"] == first["id"]
    assert (await _balance(api, creator))["paid_all_time"] == 6000  # not 12000
    listed = (await api.get("/payouts", headers=auth(creator))).json()
    assert listed["total"] == 1


async def test_reusing_a_key_for_a_different_amount_is_refused(api, intel):
    _, creator, _ = await _earner(api, intel)
    await _withdraw(api, creator, 5000, key="same-key-1")
    r = await _withdraw(api, creator, 6000, key="same-key-1")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "idempotency_conflict"


async def test_two_simultaneous_withdrawals_cannot_spend_the_same_money(api, intel):
    _, creator, _ = await _earner(api, intel)  # ₦6,000 payable
    results = await asyncio.gather(_withdraw(api, creator, 5000), _withdraw(api, creator, 5000))
    codes = sorted(r.status_code for r in results)
    assert codes == [201, 409], [r.text for r in results]
    b = await _balance(api, creator)
    assert b["paid_all_time"] == 5000 and b["payable"] == 1000


# --- when the transfer doesn't go through ----------------------------------------------------------------------------


async def test_a_rejected_transfer_returns_the_money_to_payable(api, intel, monkeypatch):
    _, creator, _ = await _earner(api, intel)

    async def reject(self, **kw):
        raise TransferRejected("The receiving bank rejected this account.")

    monkeypatch.setattr(SandboxProvider, "create_transfer", reject)
    p = (await _withdraw(api, creator, 6000)).json()
    assert p["status"] == "failed" and "rejected" in p["failure_reason"]
    b = await _balance(api, creator)
    assert b["payable"] == 6000 and b["paid_all_time"] == 0 and b["processing"] == 0  # money is back, untouched
    inbox = (await api.get("/notifications", headers=auth(creator))).json()["items"]
    assert any(n["title"] == "Withdrawal failed" for n in inbox)

    monkeypatch.undo()
    assert (await _withdraw(api, creator, 6000)).json()["status"] == "succeeded"  # and can be withdrawn again


async def test_an_unreachable_provider_leaves_the_payout_pending_and_the_money_reserved(api, intel, monkeypatch):
    _, creator, _ = await _earner(api, intel)

    async def down(self, **kw):
        raise ProviderError("timeout")

    monkeypatch.setattr(SandboxProvider, "create_transfer", down)
    p = (await _withdraw(api, creator, 6000)).json()
    assert p["status"] == "pending"
    b = await _balance(api, creator)
    assert b["payable"] == 0 and b["processing"] == 6000  # reserved: can't be spent twice while unknown
    assert (await _withdraw(api, creator, 5000)).status_code == 409


async def test_reconciliation_sends_a_payout_that_was_reserved_but_never_sent(api, intel, monkeypatch):
    _, creator, _ = await _earner(api, intel)

    async def down(self, **kw):
        raise ProviderError("timeout")

    monkeypatch.setattr(SandboxProvider, "create_transfer", down)
    p = (await _withdraw(api, creator, 6000)).json()
    monkeypatch.undo()

    async with db_session() as db:
        from datetime import timedelta

        moved = await service.reconcile(db, older_than=timedelta(seconds=-1))
    assert moved == 1
    assert (await api.get(f"/payouts/{p['id']}", headers=auth(creator))).json()["status"] == "succeeded"
    assert (await _balance(api, creator))["paid_all_time"] == 6000
    # The provider keyed on the reference, so a second pass has nothing to do.
    async with db_session() as db:
        assert await service.reconcile(db, older_than=timedelta(seconds=-1)) == 0


async def test_a_transfer_that_settles_later_completes_by_webhook(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org, expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0})
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await earn(api, intel, sid, 12_000)  # ₦6,000
    await clear_hold(creator["user"]["id"])
    await verified_bank(api, creator, number="0123459999")  # the sandbox settles this one asynchronously

    p = (await _withdraw(api, creator, 6000)).json()
    assert p["status"] == "processing"
    assert (await _balance(api, creator))["processing"] == 6000

    body = json.dumps({"event": "transfer.success", "reference": p["reference"], "provider_reference": "SBX-1"}).encode()
    headers = {"X-Signature": sign(get_settings().payment_webhook_secret, body)}
    r = await api.post("/webhooks/payments", content=body, headers=headers)
    assert r.status_code == 200 and r.json()["handled"] is True
    assert (await api.get(f"/payouts/{p['id']}", headers=auth(creator))).json()["status"] == "succeeded"
    b = await _balance(api, creator)
    assert b["paid_all_time"] == 6000 and b["processing"] == 0


async def test_a_failed_transfer_webhook_releases_the_money_and_a_replay_is_harmless(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org, expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0})
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await earn(api, intel, sid, 12_000)  # ₦6,000
    await clear_hold(creator["user"]["id"])
    await verified_bank(api, creator, number="0123459999")
    p = (await _withdraw(api, creator, 6000)).json()

    body = json.dumps({"event": "transfer.failed", "reference": p["reference"], "failure_reason": "Account closed."}).encode()
    headers = {"X-Signature": sign(get_settings().payment_webhook_secret, body)}
    assert (await api.post("/webhooks/payments", content=body, headers=headers)).json()["handled"] is True
    assert (await api.post("/webhooks/payments", content=body, headers=headers)).json()["handled"] is True  # replay: acknowledged, no effect
    got = (await api.get(f"/payouts/{p['id']}", headers=auth(creator))).json()
    assert got["status"] == "failed" and got["failure_reason"] == "Account closed."
    assert (await _balance(api, creator))["payable"] == 6000  # 12,000 views = ₦6,000, all of it back


async def test_a_late_success_cannot_flip_a_payout_that_already_failed(api, intel, monkeypatch):
    _, creator, _ = await _earner(api, intel)

    async def reject(self, **kw):
        raise TransferRejected("Rejected.")

    monkeypatch.setattr(SandboxProvider, "create_transfer", reject)
    p = (await _withdraw(api, creator, 6000)).json()
    body = json.dumps({"event": "transfer.success", "reference": p["reference"]}).encode()
    headers = {"X-Signature": sign(get_settings().payment_webhook_secret, body)}
    await api.post("/webhooks/payments", content=body, headers=headers)
    assert (await api.get(f"/payouts/{p['id']}", headers=auth(creator))).json()["status"] == "failed"


# --- allocation ------------------------------------------------------------------------------------------------------


async def test_the_oldest_earnings_are_paid_out_first(api, intel):
    _, creator, sid = await _earner(api, intel, views=12_000)  # ₦6,000
    await earn(api, intel, sid, 28_000)  # another ₦8,000, accrued later
    await clear_hold(creator["user"]["id"])
    await _withdraw(api, creator, 6000)
    history = (await api.get("/earnings/history", headers=auth(creator))).json()["items"]
    states = {row["amount"]: row["state"] for row in history}
    assert states == {6000: "Paid", 8000: "Payable"}  # the older entry left first


async def test_a_partly_withdrawn_entry_shows_as_processing_not_payable(api, intel, monkeypatch):
    _, creator, _ = await _earner(api, intel)

    async def down(self, **kw):
        raise ProviderError("timeout")

    monkeypatch.setattr(SandboxProvider, "create_transfer", down)
    await _withdraw(api, creator, 6000)
    row = (await api.get("/earnings/history", headers=auth(creator))).json()["items"][0]
    assert row["state"] == "Processing"


async def test_allocations_always_sum_to_the_payout(api, intel):
    _, creator, sid = await _earner(api, intel, views=12_000)  # ₦6,000
    await earn(api, intel, sid, 28_000)  # another ₦8,000, accrued later
    await clear_hold(creator["user"]["id"])
    p = (await _withdraw(api, creator, 10_000)).json()  # spans both entries
    async with db_session() as db:
        total = sum(a.amount for a in await db.scalars(select(payout_models.PayoutAllocation).where(payout_models.PayoutAllocation.payout_id == p["id"])))
    assert total == Decimal("10000.00")


# --- visibility ----------------------------------------------------------------------------------------------------------


async def test_a_payout_is_visible_to_its_creator_and_admin_only(api, intel):
    _, creator, _ = await _earner(api, intel)
    other = await make_creator(api)
    p = (await _withdraw(api, creator, 5000)).json()
    assert (await api.get(f"/payouts/{p['id']}", headers=auth(other))).status_code == 404
    assert (await api.get("/payouts", headers=auth(other))).json() == {"items": [], "total": 0}


async def test_payouts_list_newest_first(api, intel):
    _, creator, _ = await _earner(api, intel, views=24_000)  # ₦12,000
    a = (await _withdraw(api, creator, 5000)).json()
    b = (await _withdraw(api, creator, 5000)).json()
    ids = [p["id"] for p in (await api.get("/payouts", headers=auth(creator))).json()["items"]]
    assert ids == [b["id"], a["id"]]


async def test_a_successful_payout_notifies_the_creator(api, intel):
    _, creator, _ = await _earner(api, intel)
    await _withdraw(api, creator, 6000)
    inbox = (await api.get("/notifications", headers=auth(creator))).json()["items"]
    note = next(n for n in inbox if n["title"] == "Transfer successful")
    assert "6,000" in note["body"] and "6789" in note["body"] and note["link"].startswith("/dashboard/payouts/receipt")
