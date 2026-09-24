"""Meta's `signed_request` format — how Facebook/Instagram/Threads send
deauthorize and data-deletion callbacks: a POST form field
`signed_request=<base64url signature>.<base64url JSON payload>`, HMAC-SHA256
of the payload with the app secret.

**Unverified against real Meta traffic** — this follows Meta's published
format, but no real app secret/webhook was available to test against
(production-api-inventory.md §F). Confirm the exact field names
(`user_id` vs `algorithm` casing, etc.) against a real callback before
relying on this in production.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json


class InvalidSignedRequest(ValueError):
    pass


def _b64url_decode(segment: str) -> bytes:
    padded = segment + "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(padded.encode())


def parse_signed_request(signed_request: str, app_secret: str) -> dict:
    try:
        encoded_sig, encoded_payload = signed_request.split(".", 1)
    except ValueError as exc:
        raise InvalidSignedRequest("Malformed signed_request.") from exc

    expected = hmac.new(app_secret.encode(), encoded_payload.encode(), hashlib.sha256).digest()
    try:
        signature = _b64url_decode(encoded_sig)
    except Exception as exc:  # noqa: BLE001
        raise InvalidSignedRequest("Malformed signature.") from exc
    if not hmac.compare_digest(signature, expected):
        raise InvalidSignedRequest("Signature does not match.")

    try:
        payload = json.loads(_b64url_decode(encoded_payload))
    except Exception as exc:  # noqa: BLE001
        raise InvalidSignedRequest("Malformed payload.") from exc
    if str(payload.get("algorithm", "")).upper() != "HMAC-SHA256":
        raise InvalidSignedRequest("Unexpected signing algorithm.")
    return payload
