"""The payment provider boundary.

Everything that touches a payment provider — collecting a campaign's pot,
resolving a bank account, sending a transfer, trusting a webhook — goes
through `PaymentProvider`. The provider is undecided (plan §26: Squad vs
Paystack; the frontend copy says Payaza), so no module may import a specific
provider; they take whatever `get_provider()` returns.

Rules every implementation must keep:

- Amounts are `Decimal` naira, not kobo and not float.
- `reference` is *our* identifier and doubles as the idempotency key: asking
  for the same reference twice must not move money twice.
- Failures are exceptions from this module (`ProviderError` and friends),
  never a provider's raw exception, so callers can decide retry vs. stop.
- `verify_webhook` must be constant-time and must not parse before it has
  verified — an unsigned body is never trusted.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Protocol


class ProviderError(RuntimeError):
    """The provider failed or is unreachable. Safe to retry later."""


class AccountNotFound(ProviderError):
    """The bank account doesn't exist (or the provider can't resolve it)."""


class TransferRejected(ProviderError):
    """The provider refused this transfer. Retrying the same request won't help."""


@dataclass(frozen=True)
class Bank:
    code: str
    name: str


@dataclass(frozen=True)
class CollectionAccount:
    """Where a brand sends the money to fund a campaign."""

    bank_name: str
    account_number: str
    account_name: str
    provider_reference: str


@dataclass(frozen=True)
class CollectionStatus:
    received: bool
    amount_received: Decimal = Decimal("0")


@dataclass(frozen=True)
class ResolvedAccount:
    account_name: str
    account_number: str
    bank_code: str


class TransferStatus(str, enum.Enum):
    pending = "pending"
    success = "success"
    failed = "failed"


@dataclass(frozen=True)
class TransferResult:
    status: TransferStatus
    provider_reference: str | None = None
    failure_reason: str | None = None


class WebhookKind(str, enum.Enum):
    collection_received = "collection.received"
    transfer_success = "transfer.success"
    transfer_failed = "transfer.failed"


@dataclass(frozen=True)
class WebhookEvent:
    kind: WebhookKind
    #: Our reference (funding order or payout), echoed back by the provider.
    reference: str
    provider_reference: str | None = None
    amount: Decimal | None = None
    failure_reason: str | None = None


class PaymentProvider(Protocol):
    name: str
    #: True for a provider that never moves real money. Surfaced in API
    #: responses so nobody mistakes a sandbox transfer for a real one.
    sandbox: bool

    async def create_collection(self, *, reference: str, amount: Decimal, description: str) -> CollectionAccount: ...

    async def check_collection(
        self, *, reference: str, provider_reference: str | None, expected_amount: Decimal
    ) -> CollectionStatus: ...

    async def list_banks(self) -> list[Bank]: ...

    async def resolve_account(self, *, account_number: str, bank_code: str) -> ResolvedAccount: ...

    async def create_transfer(
        self,
        *,
        reference: str,
        amount: Decimal,
        account_number: str,
        bank_code: str,
        account_name: str,
        narration: str,
    ) -> TransferResult: ...

    async def get_transfer(self, *, reference: str) -> TransferResult: ...

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool: ...

    def parse_webhook(self, body: bytes) -> WebhookEvent | None: ...
