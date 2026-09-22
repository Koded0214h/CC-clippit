from datetime import datetime

from pydantic import BaseModel

from core.money import Money


class ReceiptVerifyOut(BaseModel):
    reference: str
    #: funding | payout | refund
    type: str
    amount: Money
    status: str
    issuer: str = "Clippit"
    date: datetime
    #: Proves this response matches an unaltered server record — not a
    #: cryptographic signature over a document (there's no PDF yet, see
    #: production-api-inventory.md §J), just a tamper check on these facts.
    digest: str
