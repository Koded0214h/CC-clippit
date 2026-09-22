import uuid
from datetime import datetime

from pydantic import BaseModel

from core.money import Money


class EarningsSummary(BaseModel):
    """The Earnings screen and the money card on the dashboard."""

    #: Withdrawable now: past the hold and not already requested.
    payable: Money
    #: Earned but still inside the holding period.
    in_hold: Money
    #: Requested and not yet settled with the bank.
    processing: Money
    paid_all_time: Money
    #: Everything ever accrued (payable + in_hold + processing + paid).
    total_accrued: Money
    lifetime_views: int
    completed_payouts: int
    #: Accrued in the last 7 days.
    added_this_week: Money
    hold_days: int
    #: When the next held amount becomes payable.
    next_clears_at: datetime | None
    last_earned_at: datetime | None
    min_withdrawal: int
    active_clips: int


class EarningRow(BaseModel):
    id: uuid.UUID
    date: datetime
    submission_id: uuid.UUID
    clip: str
    campaign_slug: str
    campaign_title: str
    brand: str | None
    billable_views: int
    amount: Money
    #: Accrued | Payable | Processing | Paid
    state: str
    payable_at: datetime


class EarningsHistory(BaseModel):
    items: list[EarningRow]
    total: int


class EarningEntryDetail(BaseModel):
    """One immutable accrual, traced back to the platform reading that
    justified it — "every naira traces to a platform snapshot"
    (production-api-inventory.md Part VIII)."""

    id: uuid.UUID
    submission_id: uuid.UUID
    campaign_id: uuid.UUID
    campaign_title: str
    campaign_slug: str
    clip_title: str | None
    brand: str | None
    #: Views gained since the previous entry, and the cumulative reading
    #: this entry settled against — the whole-thousands math is
    #: `views_total // 1000 - (thousands already billed before this entry)`.
    billable_views: int
    views_total: int
    thousands: int
    rate_per_1000_views: float
    cap_amount: float | None
    amount: Money
    #: Payable | Accrued | Processing | Paid — see EarningRow's state.
    state: str
    accrued_at: datetime
    payable_at: datetime
    #: The Intelligence snapshot this entry billed against (decision D18);
    #: null only for entries settled before that provenance field existed.
    snapshot_id: uuid.UUID | None
    reference: str
    payout_id: uuid.UUID | None


class LeaderRow(BaseModel):
    rank: int
    creator_id: uuid.UUID
    name: str
    handle: str | None
    views: int
    earned: Money
    is_me: bool = False


class Leaderboard(BaseModel):
    period: str
    updated_at: datetime
    items: list[LeaderRow]
    #: The caller's own position, even if outside the top of the list.
    me: LeaderRow | None
