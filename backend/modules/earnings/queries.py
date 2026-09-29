"""Read models over the earnings tables: balances, history, leaderboard.

Everything here is derived. The single rule that keeps balances honest:

    payable = (entries past their hold) − (everything allocated to a payout
              that has not failed)

so money is never counted twice and a failed transfer returns its money to
`payable` just by ceasing to count.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.money import ZERO, to_decimal
from modules.auth.models import SocialAccount, User
from modules.campaigns.models import Campaign, CampaignMetric, CampaignPayoutRule
from modules.campaigns.service import brands, now
from modules.creators.models import CreatorProfile
from modules.payouts.models import Payout, PayoutAllocation, PayoutStatus
from modules.submissions.models import Submission, SubmissionStatus, VerificationStatus

from . import models, schemas


def _sum(column):
    return func.coalesce(func.sum(column), 0)


@dataclass
class Balances:
    payable: object
    in_hold: object
    processing: object
    paid: object
    total_accrued: object
    lifetime_views: int
    completed_payouts: int


async def balances(db: AsyncSession, creator_id: uuid.UUID, at: datetime | None = None) -> Balances:
    """One round trip, not seven: each figure below used to be its own
    `await db.scalar(...)`, and at ~240ms per round trip to Neon that added
    up fast. Postgres runs independent scalar subqueries in a single query
    plan, so bundling them into one `select(...)` of several subqueries
    costs one round trip total instead of one per figure — same numbers,
    same semantics, just not paid for one at a time."""
    at = at or now()
    E = models.EarningEntry

    total_sq = select(_sum(E.amount)).where(E.creator_id == creator_id).scalar_subquery()
    in_hold_sq = select(_sum(E.amount)).where(E.creator_id == creator_id, E.payable_at > at).scalar_subquery()

    def allocated_sq(*statuses):
        return (
            select(_sum(PayoutAllocation.amount))
            .join(Payout, Payout.id == PayoutAllocation.payout_id)
            .where(Payout.creator_id == creator_id, Payout.status.in_(statuses))
            .scalar_subquery()
        )

    live = (PayoutStatus.pending, PayoutStatus.processing, PayoutStatus.succeeded)
    allocated_live_sq = allocated_sq(*live)
    paid_sq = allocated_sq(PayoutStatus.succeeded)

    # An admin release hold (POST /admin/earnings/{submission_id}/hold)
    # keeps otherwise-payable money out of `payable` without touching
    # accrual — see EarningAccount.release_hold_at's docstring.
    held_sq = (
        select(_sum(E.amount))
        .join(models.EarningAccount, models.EarningAccount.submission_id == E.submission_id)
        .where(E.creator_id == creator_id, E.payable_at <= at, models.EarningAccount.release_hold_at.is_not(None))
        .scalar_subquery()
    )
    views_sq = (
        select(_sum(models.EarningAccount.cumulative_views))
        .where(models.EarningAccount.creator_id == creator_id)
        .scalar_subquery()
    )
    completed_sq = (
        select(func.count())
        .select_from(Payout)
        .where(Payout.creator_id == creator_id, Payout.status == PayoutStatus.succeeded)
        .scalar_subquery()
    )

    total, in_hold, allocated_live, paid, held, views, completed = (
        await db.execute(select(total_sq, in_hold_sq, allocated_live_sq, paid_sq, held_sq, views_sq, completed_sq))
    ).one()
    total, in_hold, allocated_live, paid, held = (
        to_decimal(total), to_decimal(in_hold), to_decimal(allocated_live), to_decimal(paid), to_decimal(held)
    )
    payable_gross = total - in_hold
    return Balances(
        payable=payable_gross - allocated_live - held,
        in_hold=in_hold,
        processing=allocated_live - paid,
        paid=paid,
        total_accrued=total,
        lifetime_views=int(views or 0),
        completed_payouts=int(completed or 0),
    )


async def summary(db: AsyncSession, creator_id: uuid.UUID) -> schemas.EarningsSummary:
    """`balances()` is its own single round trip; these four figures are
    independent of it and of each other, so they're bundled into one more
    round trip alongside it rather than four separate ones."""
    at = now()
    E = models.EarningEntry
    week_sq = (
        select(_sum(E.amount))
        .where(E.creator_id == creator_id, E.accrued_at >= at - timedelta(days=7))
        .scalar_subquery()
    )
    next_clear_sq = select(func.min(E.payable_at)).where(E.creator_id == creator_id, E.payable_at > at).scalar_subquery()
    last_earned_sq = select(func.max(E.accrued_at)).where(E.creator_id == creator_id).scalar_subquery()
    active_sq = (
        select(func.count())
        .select_from(Submission)
        .where(
            Submission.creator_id == creator_id,
            Submission.status == SubmissionStatus.submitted,
            Submission.verification_status == VerificationStatus.approved,
        )
        .scalar_subquery()
    )

    # Sequential, not asyncio.gather: a single AsyncSession/connection can't
    # run two queries concurrently. Still just two round trips total.
    b = await balances(db, creator_id, at)
    week, next_clear, last_earned, active = (
        await db.execute(select(week_sq, next_clear_sq, last_earned_sq, active_sq))
    ).one()
    week = to_decimal(week)
    settings = get_settings()
    return schemas.EarningsSummary(
        payable=b.payable, in_hold=b.in_hold, processing=b.processing, paid_all_time=b.paid,
        total_accrued=b.total_accrued, lifetime_views=b.lifetime_views, completed_payouts=b.completed_payouts,
        added_this_week=week, hold_days=settings.earnings_hold_days, next_clears_at=next_clear,
        last_earned_at=last_earned, min_withdrawal=settings.min_withdrawal, active_clips=int(active or 0),
    )


async def history(db: AsyncSession, creator_id: uuid.UUID, limit: int, offset: int) -> schemas.EarningsHistory:
    at = now()
    E = models.EarningEntry
    total = await db.scalar(select(func.count()).select_from(E).where(E.creator_id == creator_id))
    rows = (
        await db.execute(
            select(E, Submission.title, Campaign.title, Campaign.slug, Campaign.event_manager_id)
            .join(Submission, Submission.id == E.submission_id)
            .join(Campaign, Campaign.id == E.campaign_id)
            .where(E.creator_id == creator_id)
            .order_by(E.accrued_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    entry_ids = [r[0].id for r in rows]

    all_alloc: dict[uuid.UUID, object] = {}
    paid_alloc: dict[uuid.UUID, object] = {}
    if entry_ids:
        base = (
            select(PayoutAllocation.entry_id, _sum(PayoutAllocation.amount))
            .join(Payout, Payout.id == PayoutAllocation.payout_id)
            .where(PayoutAllocation.entry_id.in_(entry_ids))
            .group_by(PayoutAllocation.entry_id)
        )
        live = (PayoutStatus.pending, PayoutStatus.processing, PayoutStatus.succeeded)
        all_alloc = {eid: to_decimal(v) for eid, v in await db.execute(base.where(Payout.status.in_(live)))}
        paid_alloc = {eid: to_decimal(v) for eid, v in await db.execute(base.where(Payout.status == PayoutStatus.succeeded))}

    brand_map = await brands(db, {r[4] for r in rows})
    items = []
    for entry, clip_title, campaign_title, slug, org_id in rows:
        if entry.payable_at > at:
            state = "Accrued"
        elif paid_alloc.get(entry.id, ZERO) >= entry.amount:
            state = "Paid"
        elif all_alloc.get(entry.id, ZERO) > 0:
            state = "Processing"
        else:
            state = "Payable"
        items.append(
            schemas.EarningRow(
                id=entry.id, date=entry.accrued_at, submission_id=entry.submission_id,
                clip=clip_title or "Untitled clip", campaign_slug=slug, campaign_title=campaign_title,
                brand=brand_map[org_id].name if org_id in brand_map else None,
                billable_views=int(entry.billable_views), metric_type=entry.metric_type,
                billable_units=int(entry.billable_units), unit_size=int(entry.unit_size),
                amount=entry.amount, state=state, payable_at=entry.payable_at,
            )
        )
    return schemas.EarningsHistory(items=items, total=int(total or 0))


async def entry_detail(db: AsyncSession, entry_id: uuid.UUID) -> schemas.EarningEntryDetail | None:
    """One accrual with everything an appeal, a dispute, or an admin
    investigation would need to check it: the rate/cap it was billed
    under, its state in the payout pipeline, and its snapshot reference."""
    row = (
        await db.execute(
            select(models.EarningEntry, Submission.title, Campaign, CampaignPayoutRule)
            .join(Submission, Submission.id == models.EarningEntry.submission_id)
            .join(Campaign, Campaign.id == models.EarningEntry.campaign_id)
            .outerjoin(CampaignPayoutRule, CampaignPayoutRule.campaign_id == Campaign.id)
            .where(models.EarningEntry.id == entry_id)
        )
    ).first()
    if row is None:
        return None
    entry, clip_title, campaign, rule = row

    brand_map = await brands(db, {campaign.event_manager_id})
    metric = await db.scalar(
        select(CampaignMetric).where(
            CampaignMetric.campaign_id == campaign.id,
            CampaignMetric.metric_type == entry.metric_type,
        )
    )
    alloc = (
        await db.execute(
            select(PayoutAllocation.payout_id, _sum(PayoutAllocation.amount), Payout.status)
            .join(Payout, Payout.id == PayoutAllocation.payout_id)
            .where(
                PayoutAllocation.entry_id == entry_id,
                Payout.status.in_((PayoutStatus.pending, PayoutStatus.processing, PayoutStatus.succeeded)),
            )
            .group_by(PayoutAllocation.payout_id, Payout.status)
        )
    ).first()

    at = now()
    if entry.payable_at > at:
        state = "Accrued"
    elif alloc and alloc[2] == PayoutStatus.succeeded and to_decimal(alloc[1]) >= entry.amount:
        state = "Paid"
    elif alloc and to_decimal(alloc[1]) > 0:
        state = "Processing"
    else:
        state = "Payable"

    return schemas.EarningEntryDetail(
        id=entry.id, submission_id=entry.submission_id, campaign_id=entry.campaign_id,
        campaign_title=campaign.title, campaign_slug=campaign.slug, clip_title=clip_title,
        brand=brand_map[campaign.event_manager_id].name if campaign.event_manager_id in brand_map else None,
        billable_views=int(entry.billable_views), views_total=int(entry.views_total), thousands=entry.thousands,
        rate_per_1000_views=rule.rate_per_1000_views if rule else 0.0,
        metric_type=entry.metric_type, billable_units=int(entry.billable_units), unit_size=int(entry.unit_size),
        rate_amount=float(metric.rate_amount) if metric else (rule.rate_per_1000_views if rule else 0.0),
        cap_amount=rule.cap_amount if rule else None,
        amount=entry.amount, state=state, accrued_at=entry.accrued_at, payable_at=entry.payable_at,
        snapshot_id=entry.snapshot_id, reference=entry.reference, payout_id=alloc[0] if alloc else None,
    )


async def leaderboard(
    db: AsyncSession, viewer_id: uuid.UUID, *, period: str, campaign_id: uuid.UUID | None, limit: int,
    country: str | None = None,
) -> schemas.Leaderboard:
    at = now()
    E = models.EarningEntry
    A = models.EarningAccount

    country_ids: set[uuid.UUID] | None = None
    if country:
        country_ids = set(
            await db.scalars(select(CreatorProfile.user_id).where(CreatorProfile.country == country))
        )
        if not country_ids:
            return schemas.Leaderboard(period=period, scope="country" if country else "global", updated_at=at, items=[], me=None)

    if period == "week":
        query = select(E.creator_id, _sum(E.billable_views), _sum(E.amount)).where(E.accrued_at >= at - timedelta(days=7))
        if campaign_id:
            query = query.where(E.campaign_id == campaign_id)
        rows = (await db.execute(query.group_by(E.creator_id))).all()
        stats = {cid: (int(v), to_decimal(a)) for cid, v, a in rows}
    else:
        views_q = select(A.creator_id, _sum(A.cumulative_views)).group_by(A.creator_id)
        earned_q = select(E.creator_id, _sum(E.amount)).group_by(E.creator_id)
        if campaign_id:
            views_q = views_q.where(A.campaign_id == campaign_id)
            earned_q = earned_q.where(E.campaign_id == campaign_id)
        earned = {cid: to_decimal(v) for cid, v in await db.execute(earned_q)}
        stats = {cid: (int(v), earned.get(cid, ZERO)) for cid, v in await db.execute(views_q)}

    if country_ids is not None:
        stats = {cid: v for cid, v in stats.items() if cid in country_ids}

    ranked = sorted(stats.items(), key=lambda kv: (kv[1][0], kv[1][1]), reverse=True)
    ids = {cid for cid, _ in ranked}
    profiles = {p.user_id: p for p in await db.scalars(select(CreatorProfile).where(CreatorProfile.user_id.in_(ids)))} if ids else {}
    users = {u.id: u for u in await db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}
    handles: dict[uuid.UUID, str] = {}
    if ids:
        for acct in await db.scalars(select(SocialAccount).where(SocialAccount.user_id.in_(ids), SocialAccount.handle.is_not(None))):
            handles.setdefault(acct.user_id, acct.handle)

    def row(rank: int, cid: uuid.UUID) -> schemas.LeaderRow:
        profile, user = profiles.get(cid), users.get(cid)
        views, earned = stats[cid]
        return schemas.LeaderRow(
            rank=rank, creator_id=cid, name=(profile.display_name if profile else (user.full_name if user else "Creator")),
            handle=handles.get(cid), views=views, earned=earned, is_me=cid == viewer_id,
        )

    items = [row(i + 1, cid) for i, (cid, _) in enumerate(ranked[:limit])]
    me = next((row(i + 1, cid) for i, (cid, _) in enumerate(ranked) if cid == viewer_id), None)
    return schemas.Leaderboard(period=period, scope="country" if country else "global", updated_at=at, items=items, me=me)
