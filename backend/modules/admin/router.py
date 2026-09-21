"""Operator tools. Every route is admin-only, and every action that changes
money or trust state writes an audit event naming the admin — an override is
an accountable act, never a quiet edit (plan §6: Admin must not "silently edit
historical metrics or bypass ledger controls").
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from core.money import ZERO, to_decimal
from modules.audit import service as audit
from modules.audit.models import AuditEvent
from modules.auth.deps import get_current_user
from modules.auth.models import Role, User
from modules.campaigns import models as campaign_models
from modules.campaigns.models import Campaign
from modules.earnings import jobs as earnings_jobs
from modules.earnings import queries as earnings_queries
from modules.earnings.models import EarningAccount, EarningEntry
from modules.funding import models as funding_models
from modules.funding import service as funding_service
from modules.organisations.models import OrganisationProfile
from modules.payouts import models as payout_models
from modules.payouts import service as payout_service
from modules.submissions.models import Submission, SubmissionStatus, VerificationStatus

from . import schemas

router = APIRouter(prefix="/admin", tags=["admin"])


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user


@router.get("/overview", response_model=schemas.AdminOverview)
async def overview(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    async def counts(column, model, *where):
        rows = await db.execute(select(column, func.count()).select_from(model).where(*where).group_by(column))
        return {getattr(k, "value", k): int(n) for k, n in rows}

    users = await counts(User.role, User)
    campaigns = await counts(Campaign.status, Campaign)
    payouts = await counts(payout_models.Payout.status, payout_models.Payout)

    review = await db.scalar(
        select(func.count()).select_from(Submission).where(
            Submission.status == SubmissionStatus.submitted, Submission.verification_status == VerificationStatus.needs_review
        )
    )
    appeals = await db.scalar(
        select(func.count()).select_from(Submission).where(
            Submission.status == SubmissionStatus.submitted, Submission.verification_status == VerificationStatus.appealed
        )
    )
    total_accrued = to_decimal(await db.scalar(select(func.coalesce(func.sum(EarningEntry.amount), 0))))
    paid = to_decimal(
        await db.scalar(
            select(func.coalesce(func.sum(payout_models.PayoutAllocation.amount), 0))
            .join(payout_models.Payout, payout_models.Payout.id == payout_models.PayoutAllocation.payout_id)
            .where(payout_models.Payout.status == payout_models.PayoutStatus.succeeded)
        )
    )
    awaiting = await db.scalar(
        select(func.count()).select_from(funding_models.FundingOrder).where(
            funding_models.FundingOrder.status == funding_models.FundingStatus.awaiting_confirmation
        )
    )
    blocked = await db.scalar(select(func.count()).select_from(EarningAccount).where(EarningAccount.blocked_reason.is_not(None)))
    return schemas.AdminOverview(
        users=users, campaigns=campaigns, submissions_needing_review=int(review or 0), open_appeals=int(appeals or 0),
        payouts=payouts, creator_liability=total_accrued - paid, funding_awaiting_confirmation=int(awaiting or 0),
        blocked_earning_accounts=int(blocked or 0),
    )


# --- payouts ----------------------------------------------------------------------------


@router.get("/payouts", response_model=list[schemas.AdminPayoutRow])
async def list_payouts(
    status_filter: payout_models.PayoutStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(payout_models.Payout, User).join(User, User.id == payout_models.Payout.creator_id)
    if status_filter:
        query = query.where(payout_models.Payout.status == status_filter)
    rows = (await db.execute(query.order_by(payout_models.Payout.initiated_at.desc()).limit(limit).offset(offset))).all()
    return [
        schemas.AdminPayoutRow(
            id=p.id, reference=p.reference, status=p.status.value, amount=p.amount, creator_id=u.id,
            creator_email=u.email, creator_name=u.full_name, provider=p.provider,
            provider_reference=p.provider_reference, failure_reason=p.failure_reason,
            initiated_at=p.initiated_at, completed_at=p.completed_at,
        )
        for p, u in rows
    ]


async def _payout(db: AsyncSession, payout_id: uuid.UUID) -> payout_models.Payout:
    payout = await db.get(payout_models.Payout, payout_id)
    if payout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payout not found")
    return payout


@router.post("/payouts/{payout_id}/retry", response_model=schemas.AdminPayoutRow)
async def retry_payout(payout_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Re-drives a payout stuck in flight. The provider keys on the payout's
    reference, so this cannot send the money twice."""
    payout = await _payout(db, payout_id)
    if payout.status not in (payout_models.PayoutStatus.pending, payout_models.PayoutStatus.processing):
        raise HTTPException(status.HTTP_409_CONFLICT, f"This payout is {payout.status.value}.")
    audit.record(db, "admin.payout_retried", actor_id=admin.id, subject_id=payout.creator_id, reference=payout.reference)
    if payout.status == payout_models.PayoutStatus.pending:
        await payout_service.dispatch(db, payout.id)
    await db.commit()
    await db.refresh(payout)
    user = await db.get(User, payout.creator_id)
    return schemas.AdminPayoutRow(
        id=payout.id, reference=payout.reference, status=payout.status.value, amount=payout.amount,
        creator_id=user.id, creator_email=user.email, creator_name=user.full_name, provider=payout.provider,
        provider_reference=payout.provider_reference, failure_reason=payout.failure_reason,
        initiated_at=payout.initiated_at, completed_at=payout.completed_at,
    )


@router.post("/payouts/{payout_id}/fail", response_model=schemas.AdminPayoutRow)
async def fail_payout(
    payout_id: uuid.UUID,
    payload: schemas.FailPayoutRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Marks an in-flight payout failed (say, the provider confirmed the bank
    bounced it out-of-band). The money returns to the creator's payable
    balance; it is never deleted."""
    payout = await _payout(db, payout_id)
    if payout.status not in (payout_models.PayoutStatus.pending, payout_models.PayoutStatus.processing):
        raise HTTPException(status.HTTP_409_CONFLICT, f"This payout is {payout.status.value}.")
    audit.record(
        db, "admin.payout_failed", actor_id=admin.id, subject_id=payout.creator_id,
        reference=payout.reference, reason=payload.reason,
    )
    await payout_service.fail(db, payout, payload.reason)
    await db.commit()
    await db.refresh(payout)
    user = await db.get(User, payout.creator_id)
    return schemas.AdminPayoutRow(
        id=payout.id, reference=payout.reference, status=payout.status.value, amount=payout.amount,
        creator_id=user.id, creator_email=user.email, creator_name=user.full_name, provider=payout.provider,
        provider_reference=payout.provider_reference, failure_reason=payout.failure_reason,
        initiated_at=payout.initiated_at, completed_at=payout.completed_at,
    )


# --- funding ----------------------------------------------------------------------------------


@router.get("/funding", response_model=list[schemas.AdminFundingRow])
async def list_funding(
    status_filter: funding_models.FundingStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(funding_models.FundingOrder, Campaign.title).join(Campaign, Campaign.id == funding_models.FundingOrder.campaign_id)
    if status_filter:
        query = query.where(funding_models.FundingOrder.status == status_filter)
    rows = (await db.execute(query.order_by(funding_models.FundingOrder.created_at.desc()).limit(limit))).all()
    return [
        schemas.AdminFundingRow(
            id=o.id, reference=o.reference, status=o.status.value, campaign_id=o.campaign_id, campaign_title=t,
            total=o.total_amount, provider=o.provider, created_at=o.created_at, confirmed_at=o.confirmed_at,
        )
        for o, t in rows
    ]


@router.post("/funding/{order_id}/confirm", response_model=schemas.AdminFundingRow)
async def confirm_funding(
    order_id: uuid.UUID,
    payload: schemas.ConfirmFundingRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Manual reconciliation when a webhook was missed: an admin who has seen
    the money in the bank confirms the order. The amount must cover the total —
    the same rule the webhook applies — and the note is kept in the audit log."""
    order = await db.get(funding_models.FundingOrder, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Funding order not found")
    if order.status not in (funding_models.FundingStatus.awaiting_payment, funding_models.FundingStatus.awaiting_confirmation):
        raise HTTPException(status.HTTP_409_CONFLICT, f"This order is {order.status.value}.")
    received = to_decimal(payload.amount_received)
    if received < order.total_amount:
        raise HTTPException(status.HTTP_409_CONFLICT, "That amount doesn't cover the order total.")
    campaign = await db.get(Campaign, order.campaign_id)
    audit.record(
        db, "admin.funding_confirmed", actor_id=admin.id, campaign_id=order.campaign_id, amount=received,
        reference=order.reference, note=payload.note,
    )
    await funding_service.mark_confirmed(db, order, campaign, actor_id=admin.id, amount=received)
    await db.commit()
    await db.refresh(order)
    return schemas.AdminFundingRow(
        id=order.id, reference=order.reference, status=order.status.value, campaign_id=order.campaign_id,
        campaign_title=campaign.title, total=order.total_amount, provider=order.provider,
        created_at=order.created_at, confirmed_at=order.confirmed_at,
    )


# --- earnings & campaigns ------------------------------------------------------------------------


@router.get("/earnings/blocked", response_model=list[schemas.BlockedAccountRow])
async def blocked_accounts(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Submissions whose earnings are paused (trust flags, exhausted pot, cap)."""
    rows = await db.scalars(select(EarningAccount).where(EarningAccount.blocked_reason.is_not(None)).order_by(EarningAccount.updated_at.desc()))
    return [
        schemas.BlockedAccountRow(
            submission_id=a.submission_id, campaign_id=a.campaign_id, creator_id=a.creator_id, reason=a.blocked_reason,
            cumulative_views=int(a.cumulative_views), accrued=a.accrued_amount, last_settled_at=a.last_settled_at,
        )
        for a in rows
    ]


@router.post("/earnings/settle", response_model=schemas.RunResult)
async def run_settlement(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Runs one settlement tick now instead of waiting for the schedule."""
    audit.record(db, "admin.settlement_run", actor_id=admin.id)
    await db.commit()
    return schemas.RunResult(processed=await earnings_jobs.settle_tick())


@router.post("/campaigns/sweep", response_model=schemas.RunResult)
async def run_sweep(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    audit.record(db, "admin.sweep_run", actor_id=admin.id)
    await db.commit()
    return schemas.RunResult(processed=await earnings_jobs.sweep_tick())


@router.post("/organisations/{user_id}/verify-business", response_model=dict)
async def verify_business(
    user_id: uuid.UUID,
    payload: schemas.VerifyBusinessRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """The only way `business_verified` is ever set (an organisation cannot
    set it on its own profile)."""
    user = await db.get(User, user_id)
    if user is None or user.role != Role.organisation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    profile = await db.get(OrganisationProfile, user_id)
    if profile is None:
        profile = OrganisationProfile(user_id=user_id, name=user.full_name[:80])
        db.add(profile)
    profile.business_verified = payload.verified
    if payload.legal_name is not None:
        profile.business_legal_name = payload.legal_name
    audit.record(db, "admin.business_verification", actor_id=admin.id, subject_id=user_id, verified=payload.verified)
    await db.commit()
    return {"user_id": str(user_id), "business_verified": profile.business_verified, "legal_name": profile.business_legal_name}


@router.get("/audit", response_model=list[schemas.AuditRow])
async def read_audit(
    kind: str | None = None,
    campaign_id: uuid.UUID | None = None,
    submission_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(AuditEvent)
    if kind:
        query = query.where(AuditEvent.kind.like(f"{kind}%"))
    if campaign_id:
        query = query.where(AuditEvent.campaign_id == campaign_id)
    if submission_id:
        query = query.where(AuditEvent.submission_id == submission_id)
    if subject_id:
        query = query.where(AuditEvent.subject_id == subject_id)
    rows = await db.scalars(query.order_by(AuditEvent.created_at.desc()).limit(limit))
    return [
        schemas.AuditRow(
            id=e.id, created_at=e.created_at, kind=e.kind, actor_id=e.actor_id, campaign_id=e.campaign_id,
            submission_id=e.submission_id, subject_id=e.subject_id, amount=e.amount, data=e.data,
        )
        for e in rows
    ]
