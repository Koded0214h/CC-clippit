"""A tamper check for the facts in a public receipt-verification response
— not a signature over a PDF (there isn't one yet), just proof the
amount/status/date a viewer sees came from us unaltered."""

import hashlib
from datetime import datetime
from decimal import Decimal

from .config import get_settings


def digest(reference: str, amount: Decimal, status: str, at: datetime) -> str:
    settings = get_settings()
    message = f"{reference}:{amount}:{status}:{at.isoformat()}"
    return hashlib.sha256(f"{settings.jwt_secret}:{message}".encode()).hexdigest()[:32]
