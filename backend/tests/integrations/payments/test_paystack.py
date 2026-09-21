"""The Paystack adapter against a scripted Paystack (httpx.MockTransport):
request shapes, kobo conversion, reference mapping, error mapping and the
webhook signature — everything except Paystack itself."""

import hashlib
import hmac
import json
from decimal import Decimal

import httpx
import pytest

from integrations.payments.base import (
    AccountNotFound, ProviderError, TransferRejected, TransferStatus, WebhookKind,
)
from integrations.payments.paystack import PaystackProvider, from_kobo, our_reference, paystack_reference, to_kobo

KEY = "sk_test_abc123"


class FakePaystack:
    def __init__(self):
        self.calls: list[tuple[str, str, dict | None, dict]] = []
        self.routes: dict[tuple[str, str], object] = {}

    def on(self, method, path, response):
        self.routes[(method, path)] = response

    def transport(self):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content) if request.content else None
            self.calls.append((request.method, request.url.path, body, dict(request.url.params)))
            assert request.headers["authorization"] == f"Bearer {KEY}"
            route = self.routes.get((request.method, request.url.path))
            if route is None:
                return httpx.Response(404, json={"status": False, "message": "not found"})
            out = route(request) if callable(route) else route
            return out if isinstance(out, httpx.Response) else httpx.Response(200, json=out)

        return httpx.MockTransport(handler)

    def paystack(self):
        return PaystackProvider(KEY, "https://api.paystack.test", transport=self.transport())

    def sent(self, method, path):
        return [c for c in self.calls if c[0] == method and c[1] == path]


def test_kobo_conversion_is_exact():
    assert to_kobo(Decimal("507500")) == 50_750_000
    assert to_kobo(Decimal("1234.56")) == 123_456
    assert to_kobo(Decimal("0.10")) == 10
    assert from_kobo(50_750_000) == Decimal("507500")
    assert from_kobo("123456") == Decimal("1234.56")


def test_references_map_to_paystacks_rules_and_back():
    theirs = paystack_reference("CLP-260920-1847")
    assert theirs == "clippit-clp-260920-1847"
    assert 16 <= len(theirs) <= 50 and theirs == theirs.lower()
    assert paystack_reference("CLP-2609-4F1A") == "clippit-clp-2609-4f1a"
    assert our_reference(theirs) == "CLP-260920-1847" and our_reference("CLP-2609-4F1A".lower()) is None


async def test_collection_starts_a_hosted_checkout_in_kobo():
    fake = FakePaystack()
    fake.on("POST", "/transaction/initialize", {"status": True, "data": {"authorization_url": "https://checkout.paystack.test/abc", "access_code": "AC_1"}})
    got = await fake.paystack().create_collection(
        reference="CLP-2609-4F1A", amount=Decimal("507500"), description="Indomie", email="brand@example.com", method="bank"
    )
    assert got.checkout_url == "https://checkout.paystack.test/abc" and got.provider_reference == "AC_1"
    body = fake.sent("POST", "/transaction/initialize")[0][2]
    assert body["amount"] == 50_750_000 and body["email"] == "brand@example.com" and body["currency"] == "NGN"
    assert body["reference"] == "clippit-clp-2609-4f1a" and body["channels"] == ["bank_transfer"]
    assert body["metadata"]["clippit_reference"] == "CLP-2609-4F1A"


async def test_card_method_uses_the_card_channel():
    fake = FakePaystack()
    fake.on("POST", "/transaction/initialize", {"status": True, "data": {"authorization_url": "https://x", "access_code": "a"}})
    await fake.paystack().create_collection(reference="CLP-2609-4F1A", amount=Decimal("100"), description="d", email="e@x.com", method="card")
    assert fake.calls[0][2]["channels"] == ["card"]


async def test_collection_failure_is_a_provider_error():
    fake = FakePaystack()
    fake.on("POST", "/transaction/initialize", httpx.Response(400, json={"status": False, "message": "Invalid email"}))
    with pytest.raises(ProviderError, match="Invalid email"):
        await fake.paystack().create_collection(reference="CLP-2609-4F1A", amount=Decimal("1"), description="d", email="bad", method="bank")


async def test_check_collection_reads_the_verified_amount():
    fake = FakePaystack()
    fake.on("GET", "/transaction/verify/clippit-clp-2609-4f1a", {"status": True, "data": {"status": "success", "amount": 50_750_000}})
    got = await fake.paystack().check_collection(reference="CLP-2609-4F1A", provider_reference=None, expected_amount=Decimal("507500"))
    assert got.received is True and got.amount_received == Decimal("507500")


async def test_an_unpaid_or_unknown_transaction_is_not_received():
    fake = FakePaystack()
    p = fake.paystack()
    assert (await p.check_collection(reference="CLP-2609-4F1A", provider_reference=None, expected_amount=Decimal("1"))).received is False  # 404
    fake.on("GET", "/transaction/verify/clippit-clp-2609-4f1a", {"status": True, "data": {"status": "abandoned", "amount": 0}})
    assert (await p.check_collection(reference="CLP-2609-4F1A", provider_reference=None, expected_amount=Decimal("1"))).received is False


async def test_bank_list_pages_dedupes_skips_inactive_and_is_cached():
    fake = FakePaystack()
    pages = iter([
        {"status": True, "data": [{"name": "Zenith Bank", "code": "057", "active": True}, {"name": "Dead Bank", "code": "999", "active": False}], "meta": {"next": "CUR2"}},
        {"status": True, "data": [{"name": "Access Bank", "code": "044", "active": True}, {"name": "Zenith Bank", "code": "057", "active": True}], "meta": {"next": None}},
    ])
    fake.on("GET", "/bank", lambda r: next(pages))
    p = fake.paystack()
    banks = await p.list_banks()
    assert [(b.code, b.name) for b in banks] == [("044", "Access Bank"), ("057", "Zenith Bank")]
    assert fake.sent("GET", "/bank")[1][3]["next"] == "CUR2"
    await p.list_banks()
    assert len(fake.sent("GET", "/bank")) == 2  # served from cache the second time


async def test_resolve_account():
    fake = FakePaystack()
    fake.on("GET", "/bank/resolve", {"status": True, "data": {"account_number": "0123456789", "account_name": "TOBI ADEYEMI"}})
    r = await fake.paystack().resolve_account(account_number="0123456789", bank_code="058")
    assert r.account_name == "TOBI ADEYEMI"
    assert fake.calls[0][3] == {"account_number": "0123456789", "bank_code": "058"}


async def test_an_unresolvable_account_is_not_a_provider_outage():
    fake = FakePaystack()
    fake.on("GET", "/bank/resolve", httpx.Response(422, json={"status": False, "message": "Could not resolve account name"}))
    with pytest.raises(AccountNotFound):
        await fake.paystack().resolve_account(account_number="0000000000", bank_code="058")


def _transfer_fake(transfer_response):
    fake = FakePaystack()
    fake.on("POST", "/transferrecipient", {"status": True, "data": {"recipient_code": "RCP_1"}})
    fake.on("POST", "/transfer", transfer_response)
    return fake


async def test_transfer_creates_a_recipient_then_sends_kobo_with_the_mapped_reference():
    fake = _transfer_fake({"status": True, "data": {"status": "success", "transfer_code": "TRF_1"}})
    got = await fake.paystack().create_transfer(
        reference="CLP-260920-1847", amount=Decimal("6000"), account_number="0123456789", bank_code="058",
        account_name="TOBI ADEYEMI", narration="Clippit payout CLP-260920-1847",
    )
    assert got.status == TransferStatus.success and got.provider_reference == "TRF_1"
    recipient = fake.sent("POST", "/transferrecipient")[0][2]
    assert recipient == {"type": "nuban", "name": "TOBI ADEYEMI", "account_number": "0123456789", "bank_code": "058", "currency": "NGN"}
    sent = fake.sent("POST", "/transfer")[0][2]
    assert sent == {"source": "balance", "amount": 600_000, "recipient": "RCP_1", "reason": "Clippit payout CLP-260920-1847", "reference": "clippit-clp-260920-1847"}


@pytest.mark.parametrize("state,expected", [
    ("success", TransferStatus.success), ("pending", TransferStatus.pending), ("otp", TransferStatus.pending),
    ("failed", TransferStatus.failed), ("reversed", TransferStatus.failed),
])
async def test_transfer_states_map_to_ours(state, expected):
    fake = _transfer_fake({"status": True, "data": {"status": state, "transfer_code": "T", "reason": "Bank said no"}})
    got = await fake.paystack().create_transfer(reference="CLP-260920-1847", amount=Decimal("1000"), account_number="0123456789", bank_code="058", account_name="X", narration="n")
    assert got.status == expected
    if expected == TransferStatus.failed:
        assert got.failure_reason == "Bank said no"


async def test_a_retry_after_a_crash_does_not_send_twice():
    """Paystack already has this reference: return what it says, create nothing."""
    fake = _transfer_fake({"status": True, "data": {"status": "success"}})
    fake.on("GET", "/transfer/verify/clippit-clp-260920-1847", {"status": True, "data": {"status": "success", "transfer_code": "TRF_OLD"}})
    got = await fake.paystack().create_transfer(reference="CLP-260920-1847", amount=Decimal("1000"), account_number="0123456789", bank_code="058", account_name="X", narration="n")
    assert got.provider_reference == "TRF_OLD" and got.status == TransferStatus.success
    assert fake.sent("POST", "/transfer") == [] and fake.sent("POST", "/transferrecipient") == []


async def test_a_refused_recipient_is_a_rejection():
    fake = FakePaystack()
    fake.on("POST", "/transferrecipient", httpx.Response(422, json={"status": False, "message": "Invalid account number"}))
    with pytest.raises(TransferRejected, match="Invalid account number"):
        await fake.paystack().create_transfer(reference="CLP-260920-1847", amount=Decimal("1000"), account_number="1", bank_code="058", account_name="X", narration="n")


async def test_insufficient_balance_is_our_problem_not_a_rejection():
    fake = _transfer_fake(httpx.Response(400, json={"status": False, "message": "You cannot initiate third party payouts as a starter business, or balance is insufficient"}))
    with pytest.raises(ProviderError):
        await fake.paystack().create_transfer(reference="CLP-260920-1847", amount=Decimal("1000"), account_number="0123456789", bank_code="058", account_name="X", narration="n")


async def test_a_refused_transfer_is_a_rejection():
    fake = _transfer_fake(httpx.Response(400, json={"status": False, "message": "Recipient is blocked"}))
    with pytest.raises(TransferRejected, match="Recipient is blocked"):
        await fake.paystack().create_transfer(reference="CLP-260920-1847", amount=Decimal("1000"), account_number="0123456789", bank_code="058", account_name="X", narration="n")


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
async def test_outages_and_bad_keys_leave_the_outcome_unknown(status):
    fake = FakePaystack()
    fake.on("GET", "/transfer/verify/clippit-clp-260920-1847", httpx.Response(status, json={"message": "x"}))
    with pytest.raises(ProviderError):
        await fake.paystack().create_transfer(reference="CLP-260920-1847", amount=Decimal("1000"), account_number="0123456789", bank_code="058", account_name="X", narration="n")


async def test_a_network_failure_is_a_provider_error():
    def boom(request):
        raise httpx.ConnectTimeout("timed out")

    p = PaystackProvider(KEY, "https://api.paystack.test", transport=httpx.MockTransport(boom))
    with pytest.raises(ProviderError):
        await p.list_banks()


async def test_get_transfer_reads_state_and_treats_unknown_as_pending():
    fake = FakePaystack()
    p = fake.paystack()
    assert (await p.get_transfer(reference="CLP-260920-1847")).status == TransferStatus.pending  # 404: nothing known yet
    fake.on("GET", "/transfer/verify/clippit-clp-260920-1847", {"status": True, "data": {"status": "failed", "reason": "Account closed"}})
    got = await p.get_transfer(reference="CLP-260920-1847")
    assert got.status == TransferStatus.failed and got.failure_reason == "Account closed"


# --- webhooks ---------------------------------------------------------------------------------------


def _sig(body: bytes, key: str = KEY) -> str:
    return hmac.new(key.encode(), body, hashlib.sha512).hexdigest()


def test_webhook_signature_is_hmac_sha512_of_the_raw_body():
    p = PaystackProvider(KEY)
    body = b'{"event":"charge.success","data":{"reference":"clippit-x"}}'
    assert p.verify_webhook({"x-paystack-signature": _sig(body)}, body) is True
    assert p.verify_webhook({"X-Paystack-Signature": _sig(body)}, body) is True
    assert p.verify_webhook({"x-paystack-signature": _sig(body, "sk_test_other")}, body) is False
    assert p.verify_webhook({"x-paystack-signature": _sig(body)}, body + b" ") is False  # a changed body
    assert p.verify_webhook({}, body) is False
    assert p.verify_webhook({"x-paystack-signature": _sig(body).upper()}, body) is False  # exact, constant-time match


def test_charge_success_becomes_a_collection_event_with_our_reference_and_naira():
    body = json.dumps({"event": "charge.success", "data": {"reference": "clippit-clp-2609-4f1a", "amount": 50_750_000, "id": 4099}}).encode()
    ev = PaystackProvider(KEY).parse_webhook(body)
    assert ev.kind == WebhookKind.collection_received and ev.reference == "CLP-2609-4F1A"
    assert ev.amount == Decimal("507500") and ev.provider_reference == "4099"


def test_transfer_events():
    p = PaystackProvider(KEY)
    ok = p.parse_webhook(json.dumps({"event": "transfer.success", "data": {"reference": "clippit-clp-260920-1847", "transfer_code": "TRF_9"}}).encode())
    assert ok.kind == WebhookKind.transfer_success and ok.reference == "CLP-260920-1847" and ok.provider_reference == "TRF_9"
    bad = p.parse_webhook(json.dumps({"event": "transfer.failed", "data": {"reference": "clippit-clp-260920-1847", "reason": "Account closed"}}).encode())
    assert bad.kind == WebhookKind.transfer_failed and bad.failure_reason == "Account closed"
    rev = p.parse_webhook(json.dumps({"event": "transfer.reversed", "data": {"reference": "clippit-clp-260920-1847"}}).encode())
    assert rev.kind == WebhookKind.transfer_failed and "reversed" in rev.failure_reason


def test_events_we_dont_handle_or_dont_own_are_ignored():
    p = PaystackProvider(KEY)
    assert p.parse_webhook(json.dumps({"event": "customeridentification.success", "data": {"reference": "clippit-x-1234567890"}}).encode()) is None
    assert p.parse_webhook(json.dumps({"event": "charge.success", "data": {"reference": "someone-elses-ref", "amount": 1}}).encode()) is None
    assert p.parse_webhook(b"not json") is None and p.parse_webhook(b"{}") is None
