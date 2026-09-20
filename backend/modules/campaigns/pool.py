"""How much of a campaign pot is spoken for.

This is arithmetic, not a payout. Nothing here writes a ledger row or
talks to Paystack. The pot is the campaign's promised spend:

    expected_views / 1000 × rate_per_1000_views

That's the same identity the product copy uses ("₦500,000 is enough for
1M views at ₦500 / 1K"). Each live submission then owes:

    0 if views < min_views_threshold
    else min(cap_amount, views / 1000 × rate)

`views` is the latest cumulative total Intelligence has, not
`billable_views` — there is no settlement yet, so "what we'd owe if we
paid on today's numbers" is the honest figure. Allocated is capped at
the pot: the campaign cannot promise more than it holds.

Withdrawn and rejected submissions do not count.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pool:
    pot: float
    allocated: float
    remaining: float
    percent_given: float
    percent_remaining: float
    submissions_counted: int


def pot_size(expected_views: int, rate_per_1000_views: float) -> float:
    return round(expected_views / 1000.0 * rate_per_1000_views, 2)


def obligation(
    views: int | None,
    *,
    rate_per_1000_views: float,
    min_views_threshold: int,
    cap_amount: float | None,
) -> float:
    count = 0 if views is None else views
    if count < min_views_threshold:
        return 0.0
    raw = count / 1000.0 * rate_per_1000_views
    if cap_amount is not None:
        raw = min(raw, cap_amount)
    return round(raw, 2)


def summarize(pot: float, obligations: list[float]) -> Pool:
    if pot <= 0:
        return Pool(
            pot=0.0,
            allocated=0.0,
            remaining=0.0,
            percent_given=0.0,
            percent_remaining=0.0,
            submissions_counted=len(obligations),
        )
    allocated = round(min(pot, sum(obligations)), 2)
    remaining = round(pot - allocated, 2)
    return Pool(
        pot=pot,
        allocated=allocated,
        remaining=remaining,
        percent_given=round(allocated / pot * 100, 2),
        percent_remaining=round(remaining / pot * 100, 2),
        submissions_counted=len(obligations),
    )
