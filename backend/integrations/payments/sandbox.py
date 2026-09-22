"""A payment provider that never touches a network and never moves money.

Deterministic on purpose, so development and tests can exercise every
branch without a provider account:

- collection:  an account is generated from the reference; `check_collection`
               reports received (a dev has no bank to pay from).
- resolve:     any 10-digit account resolves, except numbers ending `0000`
               (not found).
- transfer:    succeeds, except accounts ending `0000` (rejected) and ending
               `9999` (accepted as pending — settles via webhook / polling).
- webhooks:    HMAC-SHA256 of the raw body with the shared secret, in the
               `X-Signature` header — the same shape most real providers use.

Every result is marked `sandbox` upstream; the app refuses to start in
`production` with this provider (see core.config / main).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal
from typing import Mapping

from core.config import get_settings

from .banks import BANKS_BY_CODE, NIGERIAN_BANKS
from .base import (
    AccountNotFound,
    Bank,
    CollectionAccount,
    CollectionStatus,
    RefundResult,
    ResolvedAccount,
    TransferRejected,
    TransferResult,
    TransferStatus,
    WebhookEvent,
    WebhookKind,
)


def sign(secret: str, body: bytes) -> str:
    """The signature this provider expects (also used by tests to build a
    valid webhook)."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class SandboxProvider:
    name = "sandbox"
    sandbox = True

    def __init__(self, webhook_secret: str | None = None) -> None:
        self._secret = webhook_secret if webhook_secret is not None else get_settings().payment_webhook_secret

    async def create_collection(
        self, *, reference: str, amount: Decimal, description: str, email: str, method: str
    ) -> CollectionAccount:
        digest = hashlib.sha256(reference.encode()).hexdigest()
        if method == "card":
            return CollectionAccount(provider_reference=f"SBX-{digest[:10].upper()}")
        number = str(int(digest[:12], 16))[:10].zfill(10)
        return CollectionAccount(
            bank_name="Sandbox Bank",
            account_number=number,
            account_name=f"CLIPPIT / {description}"[:60].upper(),
            provider_reference=f"SBX-{digest[:10].upper()}",
        )

    async def check_collection(
        self, *, reference: str, provider_reference: str | None, expected_amount: Decimal
    ) -> CollectionStatus:
        return CollectionStatus(received=True, amount_received=expected_amount)

    async def list_banks(self) -> list[Bank]:
        return list(NIGERIAN_BANKS)

    async def resolve_account(self, *, account_number: str, bank_code: str) -> ResolvedAccount:
        if bank_code not in BANKS_BY_CODE:
            raise AccountNotFound("That bank isn't supported.")
        if len(account_number) != 10 or not account_number.isdigit() or account_number.endswith("0000"):
            raise AccountNotFound("We couldn't find an account with those details.")
        return ResolvedAccount(
            account_name=f"SANDBOX ACCOUNT {account_number[-4:]}",
            account_number=account_number,
            bank_code=bank_code,
        )

    async def create_transfer(
        self,
        *,
        reference: str,
        amount: Decimal,
        account_number: str,
        bank_code: str,
        account_name: str,
        narration: str,
    ) -> TransferResult:
        if account_number.endswith("0000"):
            raise TransferRejected("The receiving bank rejected this account.")
        provider_reference = f"SBX-TRF-{hashlib.sha256(reference.encode()).hexdigest()[:10].upper()}"
        if account_number.endswith("9999"):
            return TransferResult(status=TransferStatus.pending, provider_reference=provider_reference)
        return TransferResult(status=TransferStatus.success, provider_reference=provider_reference)

    async def get_transfer(self, *, reference: str) -> TransferResult:
        provider_reference = f"SBX-TRF-{hashlib.sha256(reference.encode()).hexdigest()[:10].upper()}"
        return TransferResult(status=TransferStatus.success, provider_reference=provider_reference)

    async def create_refund(
        self, *, reference: str, collection_reference: str, amount: Decimal, reason: str
    ) -> RefundResult:
        provider_reference = f"SBX-RFD-{hashlib.sha256(reference.encode()).hexdigest()[:10].upper()}"
        return RefundResult(status=TransferStatus.success, provider_reference=provider_reference)

    async def get_refund(self, *, reference: str) -> RefundResult:
        provider_reference = f"SBX-RFD-{hashlib.sha256(reference.encode()).hexdigest()[:10].upper()}"
        return RefundResult(status=TransferStatus.success, provider_reference=provider_reference)

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool:
        supplied = headers.get("x-signature") or headers.get("X-Signature") or ""
        return hmac.compare_digest(supplied, sign(self._secret, body))

    def parse_webhook(self, body: bytes) -> WebhookEvent | None:
        try:
            payload = json.loads(body)
            kind = WebhookKind(payload["event"])
            reference = str(payload["reference"])
        except (ValueError, KeyError, TypeError):
            return None
        amount = payload.get("amount")
        return WebhookEvent(
            kind=kind,
            reference=reference,
            provider_reference=payload.get("provider_reference"),
            amount=Decimal(str(amount)) if amount is not None else None,
            failure_reason=payload.get("failure_reason"),
        )
