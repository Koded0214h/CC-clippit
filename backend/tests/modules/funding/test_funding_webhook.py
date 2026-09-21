import json

from core.config import get_settings
from integrations.payments.sandbox import sign
from tests.http_app import api, auth, campaign_body, signup  # noqa: F401


def _signed(payload: dict) -> tuple[bytes, dict]:
    body = json.dumps(payload).encode()
    return body, {"X-Signature": sign(get_settings().payment_webhook_secret, body), "Content-Type": "application/json"}


async def _order(api, org, **overrides):
    c = (await api.post("/campaigns", headers=auth(org), json=campaign_body(**overrides))).json()
    order = (await api.post(f"/campaigns/{c['id']}/funding", headers=auth(org), json={"method": "bank"})).json()
    return c, order


async def test_a_signed_collection_event_opens_the_campaign(api):
    _, org = await signup(api, "organisation")
    c, order = await _order(api, org)
    body, headers = _signed({"event": "collection.received", "reference": order["reference"], "amount": order["total"]})
    r = await api.post("/webhooks/payments", content=body, headers=headers)
    assert r.status_code == 200 and r.json() == {"received": True, "handled": True, "first_time": True}
    assert (await api.get(f"/campaigns/{c['id']}", headers=auth(org))).json()["status"] == "active"


async def test_a_replayed_event_does_nothing_the_second_time(api):
    _, org = await signup(api, "organisation")
    c, order = await _order(api, org)
    body, headers = _signed({"event": "collection.received", "reference": order["reference"], "amount": order["total"]})
    first = await api.post("/webhooks/payments", content=body, headers=headers)
    second = await api.post("/webhooks/payments", content=body, headers=headers)
    assert first.json()["first_time"] is True and second.json()["first_time"] is False
    inbox = (await api.get("/notifications", headers=auth(org))).json()
    assert [n["title"] for n in inbox["items"]].count("Campaign funded") == 1  # notified once, not twice


async def test_an_unsigned_or_forged_event_is_refused_and_opens_nothing(api):
    _, org = await signup(api, "organisation")
    c, order = await _order(api, org)
    payload = json.dumps({"event": "collection.received", "reference": order["reference"], "amount": order["total"]}).encode()
    assert (await api.post("/webhooks/payments", content=payload)).status_code == 401
    assert (await api.post("/webhooks/payments", content=payload, headers={"X-Signature": "0" * 64})).status_code == 401
    assert (await api.get(f"/campaigns/{c['id']}", headers=auth(org))).json()["status"] == "pending_funding"


async def test_a_short_payment_does_not_open_the_campaign(api):
    _, org = await signup(api, "organisation")
    c, order = await _order(api, org)
    body, headers = _signed({"event": "collection.received", "reference": order["reference"], "amount": order["total"] - 1})
    r = await api.post("/webhooks/payments", content=body, headers=headers)
    assert r.status_code == 200 and r.json()["first_time"] is False
    assert (await api.get(f"/campaigns/{c['id']}", headers=auth(org))).json()["status"] == "pending_funding"
    assert (await api.get(f"/campaigns/{c['id']}/funding", headers=auth(org))).json()["status"] == "awaiting_confirmation"


async def test_unknown_reference_and_garbage_are_acknowledged_not_errors(api):
    body, headers = _signed({"event": "collection.received", "reference": "CLP-0000-XXXX", "amount": 5})
    r = await api.post("/webhooks/payments", content=body, headers=headers)
    assert r.status_code == 200 and r.json()["handled"] is False
    junk = b"not json"
    r = await api.post("/webhooks/payments", content=junk, headers={"X-Signature": sign(get_settings().payment_webhook_secret, junk)})
    assert r.status_code == 200 and r.json()["handled"] is False


async def test_funding_endpoints_require_the_owner_and_an_existing_order(api):
    _, org = await signup(api, "organisation")
    c = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    assert (await api.get(f"/campaigns/{c['id']}/funding", headers=auth(org))).status_code == 404
    assert (await api.post(f"/campaigns/{c['id']}/funding/confirm", headers=auth(org))).status_code == 404
    assert (await api.delete(f"/campaigns/{c['id']}/funding", headers=auth(org))).status_code == 409


async def test_a_paid_claim_cannot_be_cancelled(api, monkeypatch):
    from integrations.payments import sandbox
    from integrations.payments.base import CollectionStatus

    async def not_yet(self, **kwargs):
        return CollectionStatus(received=False)

    monkeypatch.setattr(sandbox.SandboxProvider, "check_collection", not_yet)
    _, org = await signup(api, "organisation")
    c, _ = await _order(api, org)
    claimed = await api.post(f"/campaigns/{c['id']}/funding/confirm", headers=auth(org))
    assert claimed.status_code == 200 and claimed.json()["status"] == "awaiting_confirmation"
    assert claimed.json()["campaign_status"] == "pending_funding"  # the brand's word alone opens nothing
    assert (await api.delete(f"/campaigns/{c['id']}/funding", headers=auth(org))).status_code == 409
    assert (await api.post(f"/campaigns/{c['id']}/close", headers=auth(org))).status_code == 409
