"""Money is `Decimal` in code and Postgres `NUMERIC(14, 2)`, never float.

The JSON the frontend reads is a plain number (`18400`, `6000.5`) — the
`Money` alias serializes to float at the edge only, after every
computation is done in exact arithmetic.
"""

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import PlainSerializer
from sqlalchemy import Numeric

ZERO = Decimal("0.00")

#: Column type for every currency amount in the schema.
MoneyColumn = Numeric(14, 2)

Money = Annotated[Decimal, PlainSerializer(lambda value: float(value), return_type=float, when_used="json")]


def to_decimal(value: int | float | str | Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    # str() first: Decimal(0.1) carries the binary error, Decimal("0.1") doesn't.
    return Decimal(str(value))


def quantize(value: Decimal) -> Decimal:
    """Two places, half-up — the way a receipt is rounded."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def whole_thousands(views: int) -> int:
    """Partial thousands are never billed: 1,999 views is one thousand."""
    if views <= 0:
        return 0
    return int((Decimal(views) / Decimal(1000)).to_integral_value(rounding=ROUND_DOWN))
