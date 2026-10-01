"""Paystack (https://paystack.com/docs/api), behind `PaymentProvider`.

How each thing maps:

- **Collecting a campaign's pot** — a hosted *transaction*
  (`/transaction/initialize`). The brand is sent to Paystack's page and pays
  by bank transfer or card, so card details never touch Clippit and no
  dedicated-virtual-account approval is needed. Payment arrives as a
  `charge.success` webhook; `check_collection` verifies the transaction on
  demand for the "I have funded the pot" button.
- **Bank list / account names** — `/bank`, `/bank/resolve`.
- **Payouts** — a `nuban` transfer recipient, then `/transfer` from the
  Paystack balance. Outcomes arrive as `transfer.success` / `transfer.failed`
  / `transfer.reversed` webhooks and can be re-read with `/transfer/verify`.
- **Webhooks** — `x-paystack-signature` is HMAC-SHA512 of the raw body with
  the secret key.

Two Paystack facts shape the code:

1. Amounts are in **kobo** (× 100). Everything above this module is naira
   `Decimal`; the conversion happens only here.
2. A `reference` must be 16-50 characters of lowercase letters, digits, `-`
   and `_`. Ours (`CLP-260920-1847`) is shorter and upper-case, so we send
   `clippit-<ours lower-cased>` and strip it again when a webhook echoes it
   back. The mapping is deterministic and reversible — no lookup table, and
   because Paystack rejects a repeated reference, retrying the same payout
   cannot send the money twice.

Two operational things this cannot fix for you: a transfer needs Paystack
balance to draw from, and — on live accounts — transfers may require an OTP
unless that is disabled in the dashboard (Settings → Preferences). Both leave
the payout `pending` rather than failing it; an operator resolves them.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal
from typing import Mapping

import httpx

from core.cache import TTLCache
from core.config import get_settings

from .base import (
    AccountNotFound,
    Bank,
    CollectionAccount,
    CollectionStatus,
    ProviderError,
    RefundResult,
    ResolvedAccount,
    TransferRejected,
    TransferResult,
    TransferStatus,
    WebhookEvent,
    WebhookKind,
)

REFERENCE_PREFIX = "clippit-"
KOBO = Decimal(100)


def to_kobo(amount: Decimal) -> int:
    return int((amount * KOBO).to_integral_value())


def from_kobo(kobo: int | float | str) -> Decimal:
    return Decimal(str(kobo)) / KOBO


def paystack_reference(ours: str) -> str:
    """Our reference as Paystack will accept it (see the module docstring)."""
    return f"{REFERENCE_PREFIX}{ours.lower()}"


def our_reference(theirs: str) -> str | None:
    """The reverse of `paystack_reference`; None for a reference that isn't ours."""
    if not theirs.startswith(REFERENCE_PREFIX):
        return None
    return theirs[len(REFERENCE_PREFIX):].upper()


_TRANSFER_PENDING = {"pending", "otp", "received", "queued", "processing"}
_TRANSFER_FAILED = {"failed", "reversed", "rejected", "abandoned"}


def _transfer_result(data: dict, reference: str) -> TransferResult:
    state = str(data.get("status", "")).lower()
    ref = data.get("transfer_code") or reference
    if state == "success":
        return TransferResult(status=TransferStatus.success, provider_reference=ref)
    if state in _TRANSFER_FAILED:
        return TransferResult(
            status=TransferStatus.failed, provider_reference=ref,
            failure_reason=data.get("reason") or f"Paystack marked the transfer {state}.",
        )
    return TransferResult(status=TransferStatus.pending, provider_reference=ref)


class PaystackProvider:
    name = "paystack"
    sandbox = False

    def __init__(
        self,
        secret_key: str,
        base_url: str = "https://api.paystack.co",
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 20.0,
    ) -> None:
        self._key = secret_key
        self._base = base_url.rstrip("/")
        self._transport = transport
        self._timeout = timeout
        self._banks: TTLCache[str, list[Bank]] = TTLCache(ttl_seconds=6 * 3600, max_size=1)

    # -- HTTP ------------------------------------------------------------------
    async def _call(self, method: str, path: str, *, params=None, body=None) -> tuple[int, dict]:
        """(status, json). Raises `ProviderError` for anything that is not a
        definite answer about *this request* — a timeout, a 5xx, rate limiting
        or a rejected API key. 4xx answers are returned for the caller to read."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                resp = await client.request(
                    method, f"{self._base}{path}", params=params, json=body,
                    headers={"Authorization": f"Bearer {self._key}"},
                )
        except httpx.HTTPError as exc:
            raise ProviderError(f"Couldn't reach Paystack: {exc}") from exc
        if resp.status_code in (401, 403):
            raise ProviderError("Paystack rejected our API key — check PAYSTACK_SECRET_KEY.")
        if resp.status_code == 429 or resp.status_code >= 500:
            raise ProviderError(f"Paystack is unavailable ({resp.status_code}).")
        try:
            data = resp.json()
        except ValueError:
            raise ProviderError("Paystack returned a non-JSON response.") from None
        return resp.status_code, data if isinstance(data, dict) else {}

    # -- collection ------------------------------------------------------------------
    async def create_collection(
        self, *, reference: str, amount: Decimal, description: str, email: str, method: str
    ) -> CollectionAccount:
        status, body = await self._call(
            "POST", "/transaction/initialize",
            body={
                "email": email,
                "amount": to_kobo(amount),
                "currency": "NGN",
                "reference": paystack_reference(reference),
                "channels": ["card"] if method == "card" else ["bank_transfer"],
                "metadata": {"clippit_reference": reference, "description": description},
                # Without this, Paystack falls back to whatever "Callback
                # URL" is set in the dashboard — easy to leave stale (it
                # still pointed at a decommissioned host after the last
                # infra move, so paying landed on a dead page). Setting it
                # per-transaction means it's never wrong, and it's always
                # right if the frontend domain ever changes again.
                "callback_url": f"{get_settings().app_url}/brand/campaigns/new/funded",
            },
        )
        data = body.get("data") or {}
        if status != 200 or not body.get("status") or not data.get("authorization_url"):
            raise ProviderError(body.get("message") or "Paystack couldn't start the payment.")
        return CollectionAccount(
            provider_reference=data.get("access_code") or paystack_reference(reference),
            checkout_url=data["authorization_url"],
        )

    async def check_collection(
        self, *, reference: str, provider_reference: str | None, expected_amount: Decimal
    ) -> CollectionStatus:
        status, body = await self._call("GET", f"/transaction/verify/{paystack_reference(reference)}")
        if status == 404:
            return CollectionStatus(received=False)
        data = body.get("data") or {}
        if status == 200 and data.get("status") == "success":
            return CollectionStatus(received=True, amount_received=from_kobo(data.get("amount", 0)))
        return CollectionStatus(received=False)

    # -- banks -------------------------------------------------------------------------
    async def list_banks(self) -> list[Bank]:
        cached = self._banks.get("ngn")
        if cached is not None:
            return cached
        banks: dict[str, Bank] = {}
        cursor: str | None = None
        for _ in range(10):  # a hard stop: 10 pages of 100 is far more than Nigeria has
            params = {"country": "nigeria", "currency": "NGN", "perPage": 100, "use_cursor": "true"}
            if cursor:
                params["next"] = cursor
            status, body = await self._call("GET", "/bank", params=params)
            if status != 200:
                raise ProviderError(body.get("message") or "Couldn't load banks from Paystack.")
            for row in body.get("data") or []:
                if row.get("active", True) and row.get("code") and row.get("name"):
                    banks.setdefault(str(row["code"]), Bank(code=str(row["code"]), name=row["name"]))
            cursor = (body.get("meta") or {}).get("next")
            if not cursor:
                break
        result = sorted(banks.values(), key=lambda b: b.name)
        if result:
            self._banks.set("ngn", result)
        return result

    async def resolve_account(self, *, account_number: str, bank_code: str) -> ResolvedAccount:
        status, body = await self._call(
            "GET", "/bank/resolve", params={"account_number": account_number, "bank_code": bank_code}
        )
        data = body.get("data") or {}
        if status == 200 and data.get("account_name"):
            return ResolvedAccount(account_name=data["account_name"], account_number=account_number, bank_code=bank_code)
        if status in (400, 404, 422):
            raise AccountNotFound("We couldn't find an account with those details.")
        raise ProviderError(body.get("message") or "Paystack couldn't resolve that account.")

    # -- transfers ------------------------------------------------------------------------
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
        ref = paystack_reference(reference)

        # Already sent (a retry after a crash)? Paystack rejects a repeated
        # reference, so ask first rather than treat that rejection as failure.
        existing = await self._existing_transfer(ref)
        if existing is not None:
            return existing

        status, body = await self._call(
            "POST", "/transferrecipient",
            body={"type": "nuban", "name": account_name, "account_number": account_number, "bank_code": bank_code, "currency": "NGN"},
        )
        recipient = (body.get("data") or {}).get("recipient_code")
        if status not in (200, 201) or not recipient:
            raise TransferRejected(body.get("message") or "Paystack couldn't set up that recipient.")

        status, body = await self._call(
            "POST", "/transfer",
            body={"source": "balance", "amount": to_kobo(amount), "recipient": recipient, "reason": narration[:100], "reference": ref},
        )
        if status in (200, 201) and body.get("status"):
            return _transfer_result(body.get("data") or {}, ref)

        # A 4xx means the transfer was not created. Insufficient balance is our
        # problem to fix, not the creator's account's fault: leave it pending.
        message = str(body.get("message") or "Paystack refused the transfer.")
        raced = await self._existing_transfer(ref)  # the reference may have been used by a concurrent attempt
        if raced is not None:
            return raced
        if "balance" in message.lower():
            raise ProviderError(message)
        raise TransferRejected(message)

    async def _existing_transfer(self, ref: str) -> TransferResult | None:
        status, body = await self._call("GET", f"/transfer/verify/{ref}")
        if status == 200 and body.get("status") and body.get("data"):
            return _transfer_result(body["data"], ref)
        return None

    async def get_transfer(self, *, reference: str) -> TransferResult:
        ref = paystack_reference(reference)
        found = await self._existing_transfer(ref)
        return found if found is not None else TransferResult(status=TransferStatus.pending, provider_reference=ref)

    async def create_refund(
        self, *, reference: str, collection_reference: str, amount: Decimal, reason: str
    ) -> RefundResult:
        """Paystack's `/refund` doesn't accept a caller-supplied idempotency
        reference the way transfers do, so unlike `create_transfer` this
        can't check for an existing attempt first — a duplicate call here
        risks a duplicate refund. The caller (`modules.refunds.service`)
        is responsible for only calling this once per `Refund` row."""
        status, body = await self._call(
            "POST", "/refund",
            body={
                "transaction": paystack_reference(collection_reference),
                "amount": to_kobo(amount),
                "customer_note": reason[:180],
                "merchant_note": f"Clippit refund {reference}"[:180],
            },
        )
        if status not in (200, 201) or not body.get("status"):
            raise ProviderError(str(body.get("message") or "Paystack refused the refund."))
        data = body.get("data") or {}
        provider_reference = str(data.get("id") or "")
        pstatus = str(data.get("status") or "").lower()
        if pstatus in ("processed", "success", "successful"):
            return RefundResult(status=TransferStatus.success, provider_reference=provider_reference)
        if pstatus == "failed":
            return RefundResult(status=TransferStatus.failed, provider_reference=provider_reference, failure_reason="Paystack marked this refund failed.")
        return RefundResult(status=TransferStatus.pending, provider_reference=provider_reference)

    async def get_refund(self, *, reference: str) -> RefundResult:
        # Paystack has no lookup by a caller reference for refunds (unlike
        # transfers' /transfer/verify/{reference}); polling would need the
        # provider's own refund id, which the caller already has from
        # create_refund's result. Reconciliation here waits on a real
        # provider account to confirm the exact endpoint shape.
        return RefundResult(status=TransferStatus.pending)

    # -- webhooks --------------------------------------------------------------------------
    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool:
        supplied = headers.get("x-paystack-signature") or headers.get("X-Paystack-Signature") or ""
        expected = hmac.new(self._key.encode(), body, hashlib.sha512).hexdigest()
        return hmac.compare_digest(supplied, expected)

    def parse_webhook(self, body: bytes) -> WebhookEvent | None:
        try:
            payload = json.loads(body)
            event, data = str(payload["event"]), payload["data"]
            theirs = str(data["reference"])
        except (ValueError, KeyError, TypeError):
            return None
        ours = our_reference(theirs)
        if ours is None:
            return None  # not one of our references (another integration on the same account)

        if event == "charge.success":
            return WebhookEvent(
                kind=WebhookKind.collection_received, reference=ours,
                provider_reference=str(data.get("id") or ""), amount=from_kobo(data.get("amount", 0)),
            )
        if event == "transfer.success":
            return WebhookEvent(kind=WebhookKind.transfer_success, reference=ours, provider_reference=data.get("transfer_code"))
        if event in ("transfer.failed", "transfer.reversed"):
            return WebhookEvent(
                kind=WebhookKind.transfer_failed, reference=ours, provider_reference=data.get("transfer_code"),
                failure_reason=data.get("reason") or ("Paystack reversed the transfer." if event.endswith("reversed") else "The transfer failed."),
            )
        return None
