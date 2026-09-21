import pytest

from core.config import get_settings
from core.startup import UnsafeConfiguration, assert_safe_to_start, check
from integrations.payments.banks import BANKS_BY_CODE
from integrations.payments.sandbox import SandboxProvider
from integrations.payments.base import AccountNotFound, TransferRejected, TransferStatus
from tests.http_app import api, auth, signup  # noqa: F401


async def test_bank_list_needs_a_session_and_returns_codes(api):
    assert (await api.get("/banks")).status_code == 401
    _, creator = await signup(api, "creator")
    r = await api.get("/banks", headers=auth(creator))
    assert r.status_code == 200
    banks = {b["code"]: b["name"] for b in r.json()}
    assert banks["058"] == "Guaranty Trust Bank" and banks["044"] == "Access Bank" and len(banks) >= 20


async def test_sandbox_resolves_accounts_deterministically():
    p = SandboxProvider("s")
    ok = await p.resolve_account(account_number="0123456789", bank_code="058")
    assert ok.account_name == "SANDBOX ACCOUNT 6789"
    for bad in ("0123450000", "12345", "abcdefghij"):
        with pytest.raises(AccountNotFound):
            await p.resolve_account(account_number=bad, bank_code="058")
    with pytest.raises(AccountNotFound):
        await p.resolve_account(account_number="0123456789", bank_code="999")


async def test_sandbox_transfer_outcomes():
    from decimal import Decimal

    p = SandboxProvider("s")
    kw = dict(amount=Decimal("1000"), bank_code="058", account_name="X", narration="n")
    assert (await p.create_transfer(reference="r1", account_number="0123456789", **kw)).status == TransferStatus.success
    assert (await p.create_transfer(reference="r2", account_number="0123459999", **kw)).status == TransferStatus.pending
    with pytest.raises(TransferRejected):
        await p.create_transfer(reference="r3", account_number="0123450000", **kw)
    # Same reference, same answer: the reference is the idempotency key.
    a = await p.create_transfer(reference="r1", account_number="0123456789", **kw)
    b = await p.create_transfer(reference="r1", account_number="0123456789", **kw)
    assert a.provider_reference == b.provider_reference


def test_bank_codes_are_unique_and_known():
    assert BANKS_BY_CODE["057"].name == "Zenith Bank"


def test_production_refuses_the_sandbox_and_default_secrets(monkeypatch):
    settings = get_settings()
    assert check(settings) == []  # development is unrestricted
    monkeypatch.setattr(settings, "environment", "production")
    problems = " ".join(check(settings))
    assert "sandbox" in problems and "JWT_SECRET" in problems and "console" in problems
    with pytest.raises(UnsafeConfiguration):
        assert_safe_to_start(settings)
