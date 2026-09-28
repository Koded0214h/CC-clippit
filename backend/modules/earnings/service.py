"""Turning verified views into money owed — settlement.

The rules (plan §25 and the frontend's own copy), all enforced here:

- Only an **approved** submission on a **live** campaign earns.
- Nothing is owed below the campaign's minimum views.
- Billing is per **whole thousand** of *cumulative* views. Working from the
  cumulative total (not per-poll deltas) is what keeps partial thousands from
  being lost: 900 views on each of two polls is 1,800 — one thousand — not
  zero twice. A thousand once billed is never billed again, and a reading that
  drops (platforms revise counts down) never claws money back.
- A creator can earn at most the campaign's creator cap across all their clips.
- **A campaign can never pay out more than it holds.** The pot is a hard
  ceiling checked under a row lock on the campaign, so two simultaneous
  settlements cannot both spend the last of it.
- Content Intelligence flags as untrustworthy is not paid until that clears.
- Every accrual is held for `earnings_hold_days` before it can be withdrawn.

Settling is idempotent: entries carry a unique reference
`<submission>:<thousands billed after this entry>`, so a retry, a duplicate
job or a double click can never pay the same thousand twice.

This divergence from decision D18 is deliberate: Intelligence offers
`billable_views` relative to a caller-supplied snapshot. We bill from the
cumulative `metrics.views` plus the snapshot id it came from (kept on every
entry for audit). It gives the same answer, needs no extra state, and
sidesteps the partial-thousand rounding a per-delta scheme has to work around.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_FLOOR, Decimal

import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import get_settings
from core.money import ZERO, to_decimal, whole_thousands
from modules.audit import service as audit
from modules.campaigns import models as campaign_models
from modules.campaigns import service as campaign_service
from modules.performance import service as performance_service
from modules.submissions.models import Submission, SubmissionStatus, VerificationStatus

from . import models

logger = logging.getLogger("clippit.earnings")


class IntelligenceUnavailable(RuntimeError):
    """Performance or trust couldn't be read. Nothing is settled this tick."""


@dataclass
class Settlement:
    status: str  # accrued | skipped
    reason: str | None = None
    amount: Decimal = ZERO
    thousands: int = 0


def _skip(reason: str) -> Settlement:
    return Settlement(status="skipped", reason=reason)


async def _performance(client: httpx.AsyncClient, submission_id: uuid.UUID) -> tuple[dict, uuid.UUID | None] | None:
    try:
        resp = await client.get(f"/internal/submissions/{submission_id}/performance")
    except httpx.HTTPError as exc:
        raise IntelligenceUnavailable(str(exc)) from exc
    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        raise IntelligenceUnavailable(f"performance returned {resp.status_code}")
    data = resp.json()
    metrics = data.get("metrics") or {}
    if not any(metrics.get(name) is not None for name in ("views", "comments", "shares")):
        return None
    snapshot = (data.get("provenance") or {}).get("snapshot_id")
    return metrics, (uuid.UUID(snapshot) if snapshot else None)


async def _trust_status(client: httpx.AsyncClient, submission_id: uuid.UUID) -> str:
    try:
        resp = await client.get(f"/internal/submissions/{submission_id}/trust")
    except httpx.HTTPError as exc:
        raise IntelligenceUnavailable(str(exc)) from exc
    if resp.status_code == 404:
        return "insufficient_data"
    if resp.status_code >= 400:
        raise IntelligenceUnavailable(f"trust returned {resp.status_code}")
    return str(resp.json().get("status", "insufficient_data"))


async def settle_submission(
    db: AsyncSession, submission_id: uuid.UUID, client: httpx.AsyncClient, *, at: datetime | None = None
) -> Settlement:
    """Reads the current views and books whatever whole thousands are newly
    owed. The caller commits."""
    at = at or campaign_service.now()
    submission = await db.get(Submission, submission_id)
    if (
        submission is None
        or submission.status != SubmissionStatus.submitted
        or submission.verification_status != VerificationStatus.approved
    ):
        return _skip("not_approved")

    # The campaign row lock serialises every settlement in this campaign, so
    # the pot check below cannot race another submission's.
    campaign = await db.scalar(
        select(campaign_models.Campaign)
        .options(
            selectinload(campaign_models.Campaign.payout_rule),
            selectinload(campaign_models.Campaign.performance_metrics),
        )
        .where(campaign_models.Campaign.id == submission.campaign_id)
        .with_for_update()
    )
    if campaign is None or campaign.payout_rule is None:
        return _skip("no_rule")
    if campaign.status != campaign_models.CampaignStatus.active:
        return _skip("campaign_not_live")

    observed = await _performance(client, submission_id)
    if observed is None:
        if any(metric.metric_type in ("visit", "signup", "lead", "purchase") for metric in campaign.performance_metrics):
            observed_metrics, snapshot_id = {}, None
        else:
            return _skip("no_observations")
    else:
        observed_metrics, snapshot_id = observed
    views = int(observed_metrics.get("views") or 0)

    account = await db.scalar(select(models.EarningAccount).where(models.EarningAccount.submission_id == submission_id))
    if account is None:
        account = models.EarningAccount(
            submission_id=submission_id, campaign_id=campaign.id, creator_id=submission.creator_id,
            cumulative_views=0, billed_thousands=0, accrued_amount=ZERO,
        )
        db.add(account)
        await db.flush()

    if campaign.payouts_frozen:
        # Full freeze (campaigns.pause mode="full"): keep the reading current
        # so nothing is lost once resumed, but book nothing while frozen.
        account.cumulative_views = max(account.cumulative_views, views)
        account.last_settled_at = at
        return _skip("payouts_frozen")

    trust = await _trust_status(client, submission_id)
    if account.admin_trust_override is True:
        trust = "clean"  # POST /admin/submissions/{id}/trust/clear
    elif account.admin_trust_override is False:
        trust = "flagged"  # POST /admin/submissions/{id}/trust/confirm
    if trust == "flagged":
        if account.blocked_reason != "trust_flagged":
            audit.record(db, "earnings.blocked", submission_id=submission_id, campaign_id=campaign.id, reason="trust_flagged")
        account.blocked_reason = "trust_flagged"
        account.cumulative_views = max(account.cumulative_views, views)  # keep the reading; pay nothing
        account.last_settled_at = at
        return _skip("trust_flagged")
    if account.blocked_reason == "trust_flagged":
        account.blocked_reason = None
        audit.record(db, "earnings.unblocked", submission_id=submission_id, campaign_id=campaign.id)

    if campaign.performance_metrics:
        await performance_service.record_social_snapshot(
            db,
            campaign_id=campaign.id,
            creator_id=submission.creator_id,
            submission_id=submission.id,
            snapshot_id=snapshot_id,
            metrics=observed_metrics,
            occurred_at=at,
        )
        await db.flush()
        return await _settle_configured_metrics(
            db,
            campaign=campaign,
            submission=submission,
            legacy_account=account,
            snapshot_id=snapshot_id,
            at=at,
            client=client,
        )

    previous_views = int(account.cumulative_views)
    effective = max(views, previous_views)  # a downward revision never claws money back
    account.cumulative_views = effective
    account.last_settled_at = at

    rule = campaign.payout_rule
    if effective < rule.min_views_threshold:
        return _skip("below_minimum")
    new_thousands = whole_thousands(effective) - account.billed_thousands
    if new_thousands <= 0:
        return _skip("no_new_thousand")

    rate = to_decimal(rule.rate_per_1000_views)
    if rate <= 0:
        return _skip("no_rate")

    # Creator cap: whole thousands only, so a cap that isn't a multiple of the
    # rate stops at the last thousand that fits.
    if rule.cap_amount is not None:
        earned_by_creator = to_decimal(
            await db.scalar(
                select(func.coalesce(func.sum(models.EarningEntry.amount), 0)).where(
                    models.EarningEntry.campaign_id == campaign.id,
                    models.EarningEntry.creator_id == submission.creator_id,
                )
            )
        )
        room = to_decimal(rule.cap_amount) - earned_by_creator
        if room < rate:
            account.blocked_reason = "creator_cap_reached"
            return _skip("creator_cap_reached")
        new_thousands = min(new_thousands, int((room / rate).to_integral_value(rounding=ROUND_FLOOR)))

    # Per-video cap: the same whole-thousands logic as the creator cap, but
    # scoped to this one clip's own running total (`account.accrued_amount`).
    if rule.video_cap_amount is not None:
        room = to_decimal(rule.video_cap_amount) - to_decimal(account.accrued_amount)
        if room < rate:
            account.blocked_reason = "video_cap_reached"
            return _skip("video_cap_reached")
        new_thousands = min(new_thousands, int((room / rate).to_integral_value(rounding=ROUND_FLOOR)))

    # The pot is a hard ceiling.
    spent = to_decimal(
        await db.scalar(
            select(func.coalesce(func.sum(models.EarningEntry.amount), 0)).where(
                models.EarningEntry.campaign_id == campaign.id
            )
        )
    )
    affordable = int(((campaign.pot_amount - spent) / rate).to_integral_value(rounding=ROUND_FLOOR))
    if affordable < 1:
        account.blocked_reason = "pot_exhausted"
        await campaign_service.close_campaign(db, campaign, campaign_models.CloseReason.pot_empty, actor_id=None, client=client)
        return _skip("pot_exhausted")
    if new_thousands > affordable:
        new_thousands = affordable
        account.blocked_reason = "pot_exhausted"

    amount = rate * new_thousands
    entry = models.EarningEntry(
        submission_id=submission_id,
        campaign_id=campaign.id,
        creator_id=submission.creator_id,
        amount=amount,
        billable_views=max(effective - previous_views, 0),
        views_total=effective,
        thousands=new_thousands,
        snapshot_id=snapshot_id,
        reference=f"{submission_id}:{account.billed_thousands + new_thousands}",
        accrued_at=at,
        payable_at=at + timedelta(days=get_settings().earnings_hold_days),
    )
    try:
        async with db.begin_nested():
            db.add(entry)
            await db.flush()
    except IntegrityError:
        # The same thousand was already booked by a concurrent settlement.
        return _skip("already_booked")

    account.billed_thousands += new_thousands
    account.accrued_amount = to_decimal(account.accrued_amount) + amount
    account.last_snapshot_id = snapshot_id
    if account.blocked_reason == "creator_cap_reached":
        account.blocked_reason = None
    audit.record(
        db, "earnings.accrued", submission_id=submission_id, campaign_id=campaign.id, subject_id=submission.creator_id,
        amount=amount, thousands=new_thousands, views=effective, snapshot=str(snapshot_id) if snapshot_id else None,
    )

    if campaign.pot_amount - spent - amount < rate:
        # Not even one more thousand is affordable: the campaign is done.
        await campaign_service.close_campaign(db, campaign, campaign_models.CloseReason.pot_empty, actor_id=None, client=client)
    return Settlement(status="accrued", amount=amount, thousands=new_thousands)


async def _settle_configured_metrics(
    db: AsyncSession,
    *,
    campaign: campaign_models.Campaign,
    submission: Submission,
    legacy_account: models.EarningAccount,
    snapshot_id: uuid.UUID | None,
    at: datetime,
    client: httpx.AsyncClient,
) -> Settlement:
    """Settle every outcome selected by the brand from one event ledger."""
    rows = await db.execute(
        select(
            campaign_models.PerformanceEvent.event_type,
            func.coalesce(func.sum(campaign_models.PerformanceEvent.quantity), 0),
        )
        .where(
            campaign_models.PerformanceEvent.campaign_id == campaign.id,
            campaign_models.PerformanceEvent.creator_id == submission.creator_id,
            campaign_models.PerformanceEvent.submission_id == submission.id,
            campaign_models.PerformanceEvent.verification_status.in_(("verified", "confirmed")),
            campaign_models.PerformanceEvent.fraud_status == "clear",
        )
        .group_by(campaign_models.PerformanceEvent.event_type)
    )
    totals = {event_type: int(total) for event_type, total in rows}
    spent = to_decimal(
        await db.scalar(
            select(func.coalesce(func.sum(models.EarningEntry.amount), 0)).where(
                models.EarningEntry.campaign_id == campaign.id
            )
        )
    )
    total_amount = ZERO
    total_batches = 0
    blocked: str | None = None
    below_minimum = 0

    for metric in campaign.performance_metrics:
        observed_total = totals.get(metric.metric_type, 0)
        cursor = await db.scalar(
            select(models.MetricEarningAccount)
            .where(
                models.MetricEarningAccount.campaign_id == campaign.id,
                models.MetricEarningAccount.creator_id == submission.creator_id,
                models.MetricEarningAccount.submission_id == submission.id,
                models.MetricEarningAccount.metric_type == metric.metric_type,
            )
            .with_for_update()
        )
        if cursor is None:
            cursor = models.MetricEarningAccount(
                campaign_id=campaign.id,
                creator_id=submission.creator_id,
                submission_id=submission.id,
                metric_type=metric.metric_type,
            )
            db.add(cursor)
            await db.flush()
        cursor.observed_total = max(cursor.observed_total, observed_total)
        cursor.last_settled_at = at
        if observed_total < metric.min_threshold:
            below_minimum += 1
            continue
        available_batches = observed_total // metric.unit_size - cursor.billed_batches
        if available_batches <= 0:
            continue

        rate = to_decimal(metric.rate_amount)
        if rate <= 0:
            continue
        if campaign.payout_rule.cap_amount is not None:
            creator_earned = to_decimal(
                await db.scalar(
                    select(func.coalesce(func.sum(models.EarningEntry.amount), 0)).where(
                        models.EarningEntry.campaign_id == campaign.id,
                        models.EarningEntry.creator_id == submission.creator_id,
                    )
                )
            )
            room = to_decimal(campaign.payout_rule.cap_amount) - creator_earned
            available_batches = min(
                available_batches,
                max(int((room / rate).to_integral_value(rounding=ROUND_FLOOR)), 0),
            )
            if available_batches <= 0:
                blocked = "creator_cap_reached"
                continue
        if metric.metric_type in ("view", "comment", "share") and campaign.payout_rule.video_cap_amount is not None:
            video_earned = to_decimal(
                await db.scalar(
                    select(func.coalesce(func.sum(models.EarningEntry.amount), 0)).where(
                        models.EarningEntry.submission_id == submission.id
                    )
                )
            )
            room = to_decimal(campaign.payout_rule.video_cap_amount) - video_earned
            available_batches = min(
                available_batches,
                max(int((room / rate).to_integral_value(rounding=ROUND_FLOOR)), 0),
            )
            if available_batches <= 0:
                blocked = "video_cap_reached"
                continue
        pot_room = to_decimal(campaign.pot_amount) - spent
        available_batches = min(
            available_batches,
            max(int((pot_room / rate).to_integral_value(rounding=ROUND_FLOOR)), 0),
        )
        if available_batches <= 0:
            continue

        amount = rate * available_batches
        billed_units = available_batches * metric.unit_size
        next_cursor = cursor.billed_batches + available_batches
        entry = models.EarningEntry(
            submission_id=submission.id,
            campaign_id=campaign.id,
            creator_id=submission.creator_id,
            amount=amount,
            metric_type=metric.metric_type,
            billable_units=billed_units,
            unit_size=metric.unit_size,
            billable_views=billed_units if metric.metric_type == "view" else 0,
            views_total=observed_total if metric.metric_type == "view" else 0,
            thousands=available_batches,
            snapshot_id=snapshot_id if metric.metric_type in ("view", "comment", "share") else None,
            reference=(
                f"{campaign.id.hex[:10]}:{submission.id.hex[:10]}:"
                f"{metric.metric_type}:{next_cursor}"
            ),
            accrued_at=at,
            payable_at=at + timedelta(days=get_settings().earnings_hold_days),
        )
        db.add(entry)
        cursor.billed_batches = next_cursor
        cursor.accrued_amount = to_decimal(cursor.accrued_amount) + amount
        spent += amount
        total_amount += amount
        total_batches += available_batches
        if metric.metric_type == "view":
            legacy_account.cumulative_views = max(legacy_account.cumulative_views, observed_total)
            legacy_account.billed_thousands = observed_total // 1000
            legacy_account.last_snapshot_id = snapshot_id
        legacy_account.accrued_amount = to_decimal(legacy_account.accrued_amount) + amount
        audit.record(
            db,
            "earnings.accrued",
            submission_id=submission.id,
            campaign_id=campaign.id,
            subject_id=submission.creator_id,
            amount=amount,
            metric=metric.metric_type,
            units=billed_units,
            views=observed_total if metric.metric_type == "view" else None,
            snapshot=str(snapshot_id) if snapshot_id else None,
        )
        await db.flush()

    legacy_account.last_settled_at = at
    rates = [to_decimal(m.rate_amount) for m in campaign.performance_metrics if to_decimal(m.rate_amount) > 0]
    cheapest_unit = min(rates) if rates else ZERO
    # Same rule the per-view path always had: a pot that can't buy even one
    # more unit is empty, so the campaign closes and the remainder is refundable.
    if to_decimal(campaign.pot_amount) - spent < max(cheapest_unit, Decimal("0.01")):
        legacy_account.blocked_reason = "pot_exhausted"
        await campaign_service.close_campaign(
            db, campaign, campaign_models.CloseReason.pot_empty, actor_id=None, client=client
        )
    if total_amount > ZERO:
        return Settlement(status="accrued", amount=total_amount, thousands=total_batches)
    if blocked:
        legacy_account.blocked_reason = blocked
        return _skip(blocked)
    if below_minimum and below_minimum == len(campaign.performance_metrics):
        return _skip("below_minimum")
    return _skip("no_new_metric_units")


async def settle_campaign(db: AsyncSession, campaign_id: uuid.UUID, client: httpx.AsyncClient) -> int:
    """Settles every approved submission in a campaign — used to book the
    final views just before a campaign closes. Returns how many accrued."""
    ids = list(
        await db.scalars(
            select(Submission.id).where(
                Submission.campaign_id == campaign_id,
                Submission.status == SubmissionStatus.submitted,
                Submission.verification_status == VerificationStatus.approved,
            )
        )
    )
    accrued = 0
    for submission_id in ids:
        try:
            result = await settle_submission(db, submission_id, client)
        except IntelligenceUnavailable:
            continue
        await db.commit()
        accrued += result.status == "accrued"
    return accrued
