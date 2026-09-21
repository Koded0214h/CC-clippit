"""The scheduled work around earnings. Each function is one tick: safe to
run twice, safe to skip, and written so one bad submission can't stop the
others (each settles in its own session and transaction)."""

from __future__ import annotations

import logging
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.database import AsyncSessionLocal
from core.internal_client import internal_client_for
from modules.campaigns import models as campaign_models
from modules.campaigns import service as campaign_service
from modules.notifications.service import notify
from modules.submissions.models import Submission, SubmissionStatus, VerificationStatus

from . import models, service

logger = logging.getLogger("clippit.earnings.jobs")


async def settle_tick(
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal, *, client=None, limit: int = 500
) -> int:
    """Settles approved submissions on live campaigns, least-recently-read
    first. Returns how many accrued money."""
    async with session_factory() as db:
        ids = list(
            await db.scalars(
                select(Submission.id)
                .join(campaign_models.Campaign, campaign_models.Campaign.id == Submission.campaign_id)
                .outerjoin(models.EarningAccount, models.EarningAccount.submission_id == Submission.id)
                .where(
                    Submission.status == SubmissionStatus.submitted,
                    Submission.verification_status == VerificationStatus.approved,
                    campaign_models.Campaign.status == campaign_models.CampaignStatus.active,
                )
                .order_by(models.EarningAccount.last_settled_at.asc().nulls_first())
                .limit(limit)
            )
        )

    async def run(c) -> int:
        accrued = 0
        for submission_id in ids:
            async with session_factory() as db:
                try:
                    result = await service.settle_submission(db, submission_id, c)
                    await db.commit()
                    accrued += result.status == "accrued"
                except service.IntelligenceUnavailable:
                    await db.rollback()
                except Exception:  # noqa: BLE001 — one clip must not stop the tick
                    await db.rollback()
                    logger.exception("settling %s failed", submission_id)
        return accrued

    if client is not None:
        return await run(client)
    from main import app

    async with internal_client_for(app) as c:
        return await run(c)


async def sweep_tick(session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal, *, client=None) -> int:
    """Closes campaigns whose deadline has passed — after booking the views
    they earned up to that moment, so the last hours aren't lost."""
    async def run(c) -> int:
        closed = 0
        async with session_factory() as db:
            due = list(
                await db.scalars(
                    select(campaign_models.Campaign.id).where(
                        campaign_models.Campaign.status == campaign_models.CampaignStatus.active,
                        campaign_models.Campaign.ends_at <= campaign_service.now(),
                    )
                )
            )
        for campaign_id in due:
            async with session_factory() as db:
                await service.settle_campaign(db, campaign_id, c)
                campaign = await campaign_service.resolve(db, str(campaign_id))
                if campaign and campaign.status == campaign_models.CampaignStatus.active:
                    await campaign_service.close_campaign(
                        db, campaign, campaign_models.CloseReason.deadline, actor_id=None, client=c
                    )
                    closed += 1
        return closed

    if client is not None:
        return await run(client)
    from main import app

    async with internal_client_for(app) as c:
        return await run(c)


async def notify_payable_tick(session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal) -> int:
    """Tells creators when earnings clear the hold — once per entry, however
    often this runs. Groups by creator so a batch is one message."""
    async with session_factory() as db:
        entries = list(
            await db.scalars(
                select(models.EarningEntry).where(
                    models.EarningEntry.payable_at <= campaign_service.now(),
                    models.EarningEntry.payable_notified_at.is_(None),
                )
            )
        )
        by_creator = defaultdict(list)
        for entry in entries:
            by_creator[entry.creator_id].append(entry)
        stamp = campaign_service.now()
        for creator_id, items in by_creator.items():
            total = sum(e.amount for e in items)
            await notify(
                db, creator_id, "earnings_payable", "Earnings are ready to withdraw",
                f"₦{total:,.0f} cleared the holding period and is now available.", link="/dashboard/withdraw",
            )
            for entry in items:
                entry.payable_notified_at = stamp
        await db.commit()
        return len(by_creator)
