"""Operator tools. Every route is admin-only, and every action that changes
money or trust state writes an audit event naming the admin — an override is
an accountable act, never a quiet edit (plan §6: Admin must not "silently edit
historical metrics or bypass ledger controls").
"""

import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.deps import get_db
from core.email import EmailSender, get_email_sender
from core.internal_client import get_internal_client
from core.money import ZERO, to_decimal
from modules.audit import service as audit
from modules.audit.models import AuditEvent
from modules.auth.deps import get_current_user
from modules.auth.models import OperatorInvitation, Role, Session, SocialAccount, User
from modules.campaigns import models as campaign_models
from modules.campaigns import service as campaign_service
from modules.campaigns.models import Campaign
from modules.creators.models import CreatorProfile
from modules.earnings import jobs as earnings_jobs
from modules.earnings import queries as earnings_queries
from modules.earnings.models import EarningAccount, EarningEntry
from modules.earnings.schemas import EarningEntryDetail
from modules.funding import models as funding_models
from modules.funding import service as funding_service
from modules.organisations.models import OrganisationProfile
from modules.payouts import models as payout_models
from modules.payouts import service as payout_service
from modules.refunds import models as refund_models
from modules.auth import schemas as auth_schemas
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


@router.get("/audit/export")
async def export_audit(
    kind: str | None = None,
    campaign_id: uuid.UUID | None = None,
    limit: int = Query(5000, ge=1, le=20000),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    import csv
    import io

    from fastapi.responses import Response

    from core.csv_export import csv_safe

    query = select(AuditEvent)
    if kind:
        query = query.where(AuditEvent.kind.like(f"{kind}%"))
    if campaign_id:
        query = query.where(AuditEvent.campaign_id == campaign_id)
    rows = await db.scalars(query.order_by(AuditEvent.created_at.desc()).limit(limit))
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "created_at", "kind", "actor_id", "campaign_id", "submission_id", "subject_id", "amount", "data"])
    for e in rows:
        writer.writerow(
            [csv_safe(v) for v in (e.id, e.created_at.isoformat(), e.kind, e.actor_id, e.campaign_id, e.submission_id, e.subject_id, e.amount, e.data)]
        )
    audit.record(db, "admin.audit_exported", actor_id=admin.id, exported_kind=kind or "*")
    await db.commit()
    return Response(content=buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="audit.csv"'})


@router.get("/audit/{event_id}", response_model=schemas.AuditRow)
async def audit_event_detail(event_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    event = await db.get(AuditEvent, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit event not found")
    return schemas.AuditRow(
        id=event.id, created_at=event.created_at, kind=event.kind, actor_id=event.actor_id, campaign_id=event.campaign_id,
        submission_id=event.submission_id, subject_id=event.subject_id, amount=event.amount, data=event.data,
    )


# --- users (production-api-inventory.md §N) -------------------------------------


def _user_row(u: User) -> schemas.AdminUserRow:
    return schemas.AdminUserRow(
        id=u.id, email=u.email, full_name=u.full_name, role=u.role.value, email_verified=u.email_verified,
        onboarding_completed=u.onboarding_completed, suspended=u.suspended_at is not None, created_at=u.created_at,
    )


@router.get("/users", response_model=list[schemas.AdminUserRow])
async def list_users(
    role: Role | None = None,
    q: str | None = Query(None, max_length=120),
    verified: bool | None = None,
    suspended: bool | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """No risk score or "recent activity" signal is modeled yet — those
    columns from the inventory row aren't filterable here."""
    query = select(User).where(User.deleted_at.is_(None))
    if role:
        query = query.where(User.role == role)
    if q:
        like = f"%{q.strip()}%"
        query = query.where((User.email.ilike(like)) | (User.full_name.ilike(like)))
    if verified is not None:
        query = query.where(User.email_verified == verified)
    if suspended is not None:
        query = query.where(User.suspended_at.is_not(None) if suspended else User.suspended_at.is_(None))
    rows = await db.scalars(query.order_by(User.created_at.desc()).limit(limit).offset(offset))
    return [_user_row(u) for u in rows]


@router.get("/users/{user_id}", response_model=schemas.AdminUserDetail)
async def user_detail(user_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    active_sessions = await db.scalar(
        select(func.count()).select_from(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None))
    )
    connected = await db.scalar(select(func.count()).select_from(SocialAccount).where(SocialAccount.user_id == user_id))

    money_summary: dict = {}
    if user.role == Role.creator:
        b = await earnings_queries.balances(db, user_id)
        money_summary = {
            "payable": float(b.payable), "in_hold": float(b.in_hold), "processing": float(b.processing),
            "paid": float(b.paid), "lifetime_views": b.lifetime_views,
        }
    elif user.role == Role.organisation:
        campaigns_count = await db.scalar(select(func.count()).select_from(Campaign).where(Campaign.event_manager_id == user_id))
        funded = await db.scalar(
            select(func.coalesce(func.sum(funding_models.FundingOrder.total_amount), 0)).where(
                funding_models.FundingOrder.organisation_id == user_id,
                funding_models.FundingOrder.status == funding_models.FundingStatus.confirmed,
            )
        )
        money_summary = {"campaigns": int(campaigns_count or 0), "total_funded": float(to_decimal(funded))}

    audit_rows = await db.scalars(
        select(AuditEvent).where((AuditEvent.actor_id == user_id) | (AuditEvent.subject_id == user_id))
        .order_by(AuditEvent.created_at.desc()).limit(20)
    )
    return schemas.AdminUserDetail(
        **_user_row(user).model_dump(), active_sessions=int(active_sessions or 0), connected_platforms=int(connected or 0),
        money_summary=money_summary, suspension_scopes=list(user.suspension_scopes), suspension_reason=user.suspension_reason,
        suspension_expires_at=user.suspension_expires_at,
        recent_audit=[
            schemas.AuditRow(
                id=e.id, created_at=e.created_at, kind=e.kind, actor_id=e.actor_id, campaign_id=e.campaign_id,
                submission_id=e.submission_id, subject_id=e.subject_id, amount=e.amount, data=e.data,
            )
            for e in audit_rows
        ],
    )


@router.post("/users/{user_id}/suspend", response_model=schemas.AdminUserDetail)
async def suspend_user(
    user_id: uuid.UUID, payload: schemas.SuspendUserRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.role == Role.admin:
        raise HTTPException(status.HTTP_409_CONFLICT, "Admin accounts can't be suspended here.")
    user.suspended_at = datetime.now(timezone.utc)
    user.suspension_scopes = payload.scopes
    user.suspension_reason = payload.reason
    user.suspension_expires_at = (
        datetime.now(timezone.utc) + timedelta(days=payload.duration_days) if payload.duration_days else None
    )
    audit.record(db, "admin.user_suspended", actor_id=admin.id, subject_id=user_id, scopes=payload.scopes, reason=payload.reason)
    await db.commit()
    return await user_detail(user_id, admin, db)


@router.post("/users/{user_id}/restore", response_model=schemas.AdminUserDetail)
async def restore_user(user_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    user.suspended_at = None
    user.suspension_scopes = []
    user.suspension_reason = None
    user.suspension_expires_at = None
    audit.record(db, "admin.user_restored", actor_id=admin.id, subject_id=user_id)
    await db.commit()
    return await user_detail(user_id, admin, db)


# --- submissions / trust ---------------------------------------------------------


async def _submission_row(db: AsyncSession, s: Submission, account: EarningAccount | None) -> schemas.AdminSubmissionRow:
    campaign = await db.get(Campaign, s.campaign_id)
    creator_profile = await db.get(CreatorProfile, s.creator_id)
    creator = await db.get(User, s.creator_id)
    return schemas.AdminSubmissionRow(
        id=s.id, campaign_id=s.campaign_id, campaign_title=campaign.title if campaign else "",
        creator_id=s.creator_id, creator_name=(creator_profile.display_name if creator_profile else (creator.full_name if creator else "")),
        platform=s.platform, status=s.status.value, verification_status=s.verification_status.value,
        flagged=bool(account and account.blocked_reason == "trust_flagged"),
        cumulative_views=int(account.cumulative_views) if account else 0,
        accrued=account.accrued_amount if account else ZERO, created_at=s.created_at,
    )


@router.get("/submissions/flagged", response_model=list[schemas.AdminSubmissionRow])
async def flagged_submissions(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    """No severity/risk-rule breakdown yet — that needs a per-row live call
    into Intelligence's trust read, which this list-view deliberately
    doesn't do N times; see `GET /admin/submissions/{id}` for the full
    trust picture on one submission."""
    rows = await db.execute(
        select(Submission, EarningAccount)
        .join(EarningAccount, EarningAccount.submission_id == Submission.id)
        .where(EarningAccount.blocked_reason == "trust_flagged")
        .order_by(EarningAccount.updated_at.desc()).limit(limit).offset(offset)
    )
    return [await _submission_row(db, s, a) for s, a in rows]


@router.get("/submissions", response_model=list[schemas.AdminSubmissionRow])
async def all_submissions(
    verification_status: VerificationStatus | None = None,
    status_filter: SubmissionStatus | None = Query(None, alias="status"),
    platform: str | None = None,
    campaign_id: uuid.UUID | None = None,
    creator_id: uuid.UUID | None = None,
    flagged: bool | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(Submission).outerjoin(EarningAccount, EarningAccount.submission_id == Submission.id)
    if verification_status:
        query = query.where(Submission.verification_status == verification_status)
    if status_filter:
        query = query.where(Submission.status == status_filter)
    if platform:
        query = query.where(Submission.platform == platform)
    if campaign_id:
        query = query.where(Submission.campaign_id == campaign_id)
    if creator_id:
        query = query.where(Submission.creator_id == creator_id)
    if flagged is not None:
        query = query.where(
            EarningAccount.blocked_reason == "trust_flagged" if flagged else EarningAccount.blocked_reason.is_distinct_from("trust_flagged")
        )
    rows = await db.scalars(query.order_by(Submission.created_at.desc()).limit(limit).offset(offset))
    submissions = list(rows)
    accounts = {
        a.submission_id: a
        for a in await db.scalars(select(EarningAccount).where(EarningAccount.submission_id.in_([s.id for s in submissions])))
    }
    return [await _submission_row(db, s, accounts.get(s.id)) for s in submissions]


@router.get("/submissions/random-audits", response_model=list[schemas.RandomAuditRow])
async def random_audits(
    limit: int = Query(20, ge=1, le=100), admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    """A statistically unbiased sample of *unflagged* submissions — see
    `modules.intelligence.contracts.ReviewSource`'s docstring for why
    this exists: a model trained only on the flagged queue's own labels
    never learns what it's missing. Registered ahead of
    `GET /submissions/{submission_id}` below — a literal path segment
    must be matched before a dynamic one that would otherwise swallow it."""
    rows = await db.execute(
        select(Submission, Campaign)
        .join(Campaign, Campaign.id == Submission.campaign_id)
        .outerjoin(EarningAccount, EarningAccount.submission_id == Submission.id)
        .where(EarningAccount.blocked_reason.is_distinct_from("trust_flagged"))
        .order_by(func.random())
        .limit(limit)
    )
    return [
        schemas.RandomAuditRow(submission_id=s.id, campaign_id=c.id, creator_id=s.creator_id, platform=s.platform, created_at=s.created_at)
        for s, c in rows
    ]


@router.get("/submissions/{submission_id}", response_model=schemas.AdminSubmissionDetail)
async def submission_detail(
    submission_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_internal_client),
):
    s = await db.get(Submission, submission_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    account = await db.get(EarningAccount, submission_id)
    row = await _submission_row(db, s, account)

    trust = None
    try:
        resp = await client.get(f"/internal/submissions/{submission_id}/trust")
        if resp.status_code < 400:
            trust = resp.json()
    except httpx.HTTPError:
        pass

    return schemas.AdminSubmissionDetail(
        **row.model_dump(), url=s.url, verification_summary=s.verification_summary, trust=trust,
        admin_trust_override=account.admin_trust_override if account else None,
        hold_active=bool(account and account.release_hold_at is not None),
        hold_reason=account.hold_reason if account else None,
    )


async def _get_account(db: AsyncSession, submission_id: uuid.UUID) -> EarningAccount:
    account = await db.get(EarningAccount, submission_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No earning account for this submission yet.")
    return account


@router.post("/submissions/{submission_id}/trust/clear", response_model=schemas.AdminSubmissionDetail)
async def clear_trust_flag(
    submission_id: uuid.UUID, payload: schemas.TrustDecisionRequest, admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db), client: httpx.AsyncClient = Depends(get_internal_client),
):
    """Forces accrual to resume even if Intelligence's own read is still
    `flagged` — see `EarningAccount.admin_trust_override`'s docstring.
    Also records a `flagged_queue` review with Intelligence so this
    becomes a labelled training example, not just a local override."""
    account = await _get_account(db, submission_id)
    account.admin_trust_override = True
    if account.blocked_reason == "trust_flagged":
        account.blocked_reason = None
    try:
        await client.post(
            f"/internal/submissions/{submission_id}/trust/review",
            json={"outcome": "legitimate", "source": "flagged_queue", "reviewer_id": str(admin.id), "notes": payload.note},
        )
    except httpx.HTTPError:
        pass
    audit.record(db, "admin.trust_cleared", actor_id=admin.id, submission_id=submission_id, note=payload.note)
    await db.commit()
    return await submission_detail(submission_id, admin, db, client)


@router.post("/submissions/{submission_id}/trust/confirm", response_model=schemas.AdminSubmissionDetail)
async def confirm_trust_fraud(
    submission_id: uuid.UUID, payload: schemas.TrustDecisionRequest, admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db), client: httpx.AsyncClient = Depends(get_internal_client),
):
    """Forces the block to stay even if Intelligence's own read later
    clears, and stops tracking — a confirmed-fraud submission earns
    nothing more going forward. Does not claw back money already paid
    out; that's a separate, human recovery/sanction action."""
    account = await _get_account(db, submission_id)
    account.admin_trust_override = False
    account.blocked_reason = "trust_flagged"
    try:
        await client.post(
            f"/internal/submissions/{submission_id}/trust/review",
            json={"outcome": "fraudulent", "source": "flagged_queue", "reviewer_id": str(admin.id), "notes": payload.note},
        )
    except httpx.HTTPError:
        pass
    try:
        await client.post(f"/internal/submissions/{submission_id}/tracking/stop")
    except httpx.HTTPError:
        pass
    audit.record(db, "admin.trust_confirmed_fraud", actor_id=admin.id, submission_id=submission_id, note=payload.note)
    await db.commit()
    return await submission_detail(submission_id, admin, db, client)


# --- campaigns ---------------------------------------------------------------


@router.get("/campaigns", response_model=list[schemas.AdminCampaignRow])
async def list_campaigns_admin(
    status_filter: campaign_models.CampaignStatus | None = Query(None, alias="status"),
    organisation_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(Campaign)
    if status_filter:
        query = query.where(Campaign.status == status_filter)
    if organisation_id:
        query = query.where(Campaign.event_manager_id == organisation_id)
    campaigns = list(await db.scalars(query.order_by(Campaign.created_at.desc()).limit(limit).offset(offset)))
    spent = await campaign_service.spent_by_campaign(db, [c.id for c in campaigns])
    counts = await campaign_service.counts_by_campaign(db, [c.id for c in campaigns])
    brand_map = await campaign_service.brands(db, {c.event_manager_id for c in campaigns})
    return [
        schemas.AdminCampaignRow(
            id=c.id, slug=c.slug, title=c.title, organisation_id=c.event_manager_id,
            organisation_name=brand_map[c.event_manager_id].name if c.event_manager_id in brand_map else "",
            status=c.status.value, pot=c.pot_amount, spent=spent.get(c.id, ZERO), needs_review=counts[c.id].review,
            created_at=c.created_at,
        )
        for c in campaigns
    ]


@router.get("/campaigns/{campaign_ref}", response_model=schemas.AdminCampaignDetail)
async def campaign_detail_admin(campaign_ref: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    campaign = await campaign_service.resolve(db, campaign_ref)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    spent = (await campaign_service.spent_by_campaign(db, [campaign.id])).get(campaign.id, ZERO)
    counts = (await campaign_service.counts_by_campaign(db, [campaign.id]))[campaign.id]
    brand_map = await campaign_service.brands(db, {campaign.event_manager_id})
    return schemas.AdminCampaignDetail(
        id=campaign.id, slug=campaign.slug, title=campaign.title, organisation_id=campaign.event_manager_id,
        organisation_name=brand_map[campaign.event_manager_id].name if campaign.event_manager_id in brand_map else "",
        status=campaign.status.value, pot=campaign.pot_amount, spent=spent, needs_review=counts.review,
        created_at=campaign.created_at, platforms=list(campaign.platforms), duration_days=campaign.duration_days,
        ends_at=campaign.ends_at, submissions=counts.submissions,
    )


@router.post("/campaigns/{campaign_ref}/pause", response_model=schemas.AdminCampaignDetail)
async def emergency_pause(
    campaign_ref: str, payload: schemas.EmergencyActionRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    """Distinct from the brand's own pause: this is an operator action
    taken over the brand's head, so it gets its own audit kind."""
    campaign = await campaign_service.resolve(db, campaign_ref)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    if campaign.status != campaign_models.CampaignStatus.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a live campaign can be paused.")
    campaign.accepting_entries = False
    audit.record(db, "admin.campaign_paused", actor_id=admin.id, campaign_id=campaign.id, reason=payload.reason)
    await db.commit()
    return await campaign_detail_admin(campaign_ref, admin, db)


@router.post("/campaigns/{campaign_ref}/close", response_model=schemas.AdminCampaignDetail)
async def emergency_close(
    campaign_ref: str, payload: schemas.EmergencyActionRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_internal_client),
):
    campaign = await campaign_service.resolve(db, campaign_ref)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    if campaign.status == campaign_models.CampaignStatus.closed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Campaign is already closed.")

    from modules.earnings import service as earnings_service

    if campaign.status == campaign_models.CampaignStatus.active:
        await earnings_service.settle_campaign(db, campaign.id, client)
        await db.refresh(campaign)
    if campaign.status != campaign_models.CampaignStatus.closed:
        await campaign_service.close_campaign(db, campaign, campaign_models.CloseReason.admin, actor_id=admin.id, client=client)
    audit.record(db, "admin.campaign_closed", actor_id=admin.id, campaign_id=campaign.id, reason=payload.reason)
    await db.commit()
    return await campaign_detail_admin(campaign_ref, admin, db)


# --- earnings ------------------------------------------------------------------


@router.get("/earnings", response_model=list[schemas.AdminEarningEntryRow])
async def list_earning_entries(
    creator_id: uuid.UUID | None = None,
    campaign_id: uuid.UUID | None = None,
    submission_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(EarningEntry).outerjoin(EarningAccount, EarningAccount.submission_id == EarningEntry.submission_id)
    if creator_id:
        query = query.where(EarningEntry.creator_id == creator_id)
    if campaign_id:
        query = query.where(EarningEntry.campaign_id == campaign_id)
    if submission_id:
        query = query.where(EarningEntry.submission_id == submission_id)
    rows = list(await db.scalars(query.order_by(EarningEntry.accrued_at.desc()).limit(limit).offset(offset)))
    accounts = {
        a.submission_id: a
        for a in await db.scalars(select(EarningAccount).where(EarningAccount.submission_id.in_([e.submission_id for e in rows])))
    }
    return [
        schemas.AdminEarningEntryRow(
            id=e.id, submission_id=e.submission_id, campaign_id=e.campaign_id, creator_id=e.creator_id,
            amount=e.amount, billable_views=int(e.billable_views), thousands=e.thousands, payable_at=e.payable_at,
            accrued_at=e.accrued_at, on_hold=bool(accounts.get(e.submission_id) and accounts[e.submission_id].release_hold_at),
            trust_blocked=bool(accounts.get(e.submission_id) and accounts[e.submission_id].blocked_reason == "trust_flagged"),
        )
        for e in rows
    ]


@router.get("/earnings/{entry_id}", response_model=EarningEntryDetail)
async def earning_entry_detail_admin(entry_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Same shape a creator's own `GET /earnings/entries/{id}` returns —
    the admin route just skips the ownership check."""
    detail = await earnings_queries.entry_detail(db, entry_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    return detail


@router.post("/earnings/{submission_id}/hold", response_model=schemas.AdminSubmissionDetail)
async def hold_earnings(
    submission_id: uuid.UUID, payload: schemas.HoldRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_internal_client),
):
    """Blocks payable money from being reserved into a payout without
    touching accrual — see `EarningAccount.release_hold_at`'s docstring.
    Money that's already inside a payout's allocation isn't clawed back;
    this only stops *new* reservations."""
    account = await _get_account(db, submission_id)
    account.release_hold_at = datetime.now(timezone.utc)
    account.hold_reason = payload.reason
    audit.record(db, "admin.earnings_held", actor_id=admin.id, submission_id=submission_id, reason=payload.reason)
    await db.commit()
    return await submission_detail(submission_id, admin, db, client)


@router.post("/earnings/{submission_id}/release", response_model=schemas.AdminSubmissionDetail)
async def release_earnings_hold(
    submission_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_internal_client),
):
    account = await _get_account(db, submission_id)
    if account.release_hold_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "There's no hold on this submission's earnings.")
    account.release_hold_at = None
    account.hold_reason = None
    audit.record(db, "admin.earnings_released", actor_id=admin.id, submission_id=submission_id)
    await db.commit()
    return await submission_detail(submission_id, admin, db, client)


# --- unified finance ledger ------------------------------------------------------


@router.get("/ledger", response_model=list[schemas.AdminLedgerRow])
async def unified_ledger(
    kind: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Funding orders, refunds, and payouts, merged and sorted — the same
    "present the existing immutable rows together" approach as the
    brand's own ledger (`modules.organisations.ledger`), just unscoped."""
    rows: list[schemas.AdminLedgerRow] = []
    if kind in (None, "funding"):
        orders = await db.scalars(select(funding_models.FundingOrder).order_by(funding_models.FundingOrder.created_at.desc()).limit(limit))
        rows += [
            schemas.AdminLedgerRow(
                id=o.id, kind="funding", organisation_id=o.organisation_id, creator_id=None, campaign_id=o.campaign_id,
                amount=o.total_amount, status=o.status.value, provider=o.provider, provider_reference=o.provider_reference,
                reference=o.reference, created_at=o.created_at, settled_at=o.confirmed_at,
            )
            for o in orders
        ]
    if kind in (None, "refund"):
        refunds = await db.scalars(select(refund_models.Refund).order_by(refund_models.Refund.created_at.desc()).limit(limit))
        rows += [
            schemas.AdminLedgerRow(
                id=r.id, kind="refund", organisation_id=r.organisation_id, creator_id=None, campaign_id=r.campaign_id,
                amount=r.amount, status=r.status.value, provider=r.provider, provider_reference=r.provider_reference,
                reference=r.reference, created_at=r.created_at, settled_at=r.processed_at,
            )
            for r in refunds
        ]
    if kind in (None, "payout"):
        payouts = await db.scalars(select(payout_models.Payout).order_by(payout_models.Payout.initiated_at.desc()).limit(limit))
        rows += [
            schemas.AdminLedgerRow(
                id=p.id, kind="payout", organisation_id=None, creator_id=p.creator_id, campaign_id=None,
                amount=p.amount, status=p.status.value, provider=p.provider, provider_reference=p.provider_reference,
                reference=p.reference, created_at=p.initiated_at, settled_at=p.completed_at,
            )
            for p in payouts
        ]
    rows.sort(key=lambda r: r.created_at, reverse=True)
    return rows[offset : offset + limit]


@router.get("/ledger/export")
async def export_ledger(
    kind: str | None = None, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    import csv
    import io

    from fastapi.responses import Response

    from core.csv_export import csv_safe

    rows = await unified_ledger(kind=kind, limit=20_000, offset=0, admin=admin, db=db)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "kind", "organisation_id", "creator_id", "campaign_id", "amount", "status", "provider", "reference", "created_at", "settled_at"])
    for r in rows:
        writer.writerow(
            [
                csv_safe(v)
                for v in (
                    r.id, r.kind, r.organisation_id, r.creator_id, r.campaign_id, f"{r.amount:.2f}", r.status,
                    r.provider, r.reference, r.created_at.isoformat(), r.settled_at.isoformat() if r.settled_at else "",
                )
            ]
        )
    audit.record(db, "admin.ledger_exported", actor_id=admin.id, exported_kind=kind or "*")
    await db.commit()
    return Response(content=buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="ledger.csv"'})



@router.get("/ledger/{entry_id}", response_model=schemas.AdminLedgerRow)
async def ledger_entry_detail(entry_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    order = await db.get(funding_models.FundingOrder, entry_id)
    if order is not None:
        return schemas.AdminLedgerRow(
            id=order.id, kind="funding", organisation_id=order.organisation_id, creator_id=None, campaign_id=order.campaign_id,
            amount=order.total_amount, status=order.status.value, provider=order.provider,
            provider_reference=order.provider_reference, reference=order.reference, created_at=order.created_at,
            settled_at=order.confirmed_at,
        )
    refund = await db.get(refund_models.Refund, entry_id)
    if refund is not None:
        return schemas.AdminLedgerRow(
            id=refund.id, kind="refund", organisation_id=refund.organisation_id, creator_id=None, campaign_id=refund.campaign_id,
            amount=refund.amount, status=refund.status.value, provider=refund.provider,
            provider_reference=refund.provider_reference, reference=refund.reference, created_at=refund.created_at,
            settled_at=refund.processed_at,
        )
    payout = await db.get(payout_models.Payout, entry_id)
    if payout is not None:
        return schemas.AdminLedgerRow(
            id=payout.id, kind="payout", organisation_id=None, creator_id=payout.creator_id, campaign_id=None,
            amount=payout.amount, status=payout.status.value, provider=payout.provider,
            provider_reference=payout.provider_reference, reference=payout.reference, created_at=payout.initiated_at,
            settled_at=payout.completed_at,
        )
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Ledger entry not found")


# --- operators (production-api-inventory.md §O) ---------------------------------


@router.post("/operators/invitations", response_model=auth_schemas.AdminInvitationCreated, status_code=status.HTTP_201_CREATED)
async def invite_operator(
    payload: auth_schemas.AdminInvitationCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
    sender: EmailSender = Depends(get_email_sender),
):
    from core.security import create_admin_invite_token
    from modules.auth import emails as auth_emails

    existing = await db.scalar(select(User.id).where(User.email == payload.email))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")

    invitation = OperatorInvitation(
        email=payload.email, permissions=payload.permissions, invited_by=admin.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db.add(invitation)
    await db.flush()
    token = create_admin_invite_token(invitation.id, minutes=3 * 24 * 60)
    link = f"{get_settings().frontend_origin.split(',')[0].strip()}/admin/operators/accept?token={token}"
    audit.record(db, "admin.operator_invited", actor_id=admin.id, subject_id=invitation.id, email=payload.email)
    await db.commit()
    try:
        await sender.send(auth_emails.admin_invitation_email(payload.email, link, admin.full_name))
    except Exception:  # noqa: BLE001
        pass
    return auth_schemas.AdminInvitationCreated(
        id=invitation.id, email=invitation.email, permissions=invitation.permissions,
        expires_at=invitation.expires_at, invite_token=token,
    )


def _operator_row(u: User, last_active_at: datetime | None) -> schemas.OperatorRow:
    return schemas.OperatorRow(
        id=u.id, email=u.email, full_name=u.full_name, permissions=list(u.permissions),
        suspended=u.suspended_at is not None, invited_by=u.invited_by, last_active_at=last_active_at, created_at=u.created_at,
    )


@router.get("/operators", response_model=list[schemas.OperatorRow])
async def list_operators(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(select(User).where(User.role == Role.admin, User.deleted_at.is_(None)).order_by(User.created_at)))
    last_seen = {
        uid: seen
        for uid, seen in await db.execute(
            select(Session.user_id, func.max(Session.last_seen_at)).where(Session.user_id.in_([u.id for u in rows])).group_by(Session.user_id)
        )
    }
    return [_operator_row(u, last_seen.get(u.id)) for u in rows]


@router.patch("/operators/{operator_id}", response_model=schemas.OperatorRow)
async def update_operator(
    operator_id: uuid.UUID, payload: schemas.OperatorPatch, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    if operator_id == admin.id and payload.permissions is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't change your own permissions.")
    operator = await db.get(User, operator_id)
    if operator is None or operator.role != Role.admin:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Operator not found")
    if payload.permissions is not None:
        operator.permissions = payload.permissions
        audit.record(db, "admin.operator_permissions_changed", actor_id=admin.id, subject_id=operator_id, permissions=payload.permissions)
    await db.commit()
    last_seen = await db.scalar(select(func.max(Session.last_seen_at)).where(Session.user_id == operator_id))
    return _operator_row(operator, last_seen)


@router.post("/operators/{operator_id}/suspend", response_model=schemas.OperatorRow)
async def suspend_operator(operator_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if operator_id == admin.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't suspend your own account.")
    operator = await db.get(User, operator_id)
    if operator is None or operator.role != Role.admin:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Operator not found")
    operator.suspended_at = datetime.now(timezone.utc)
    operator.suspension_scopes = ["access"]
    operator.suspension_reason = "Operator access suspended"
    from modules.auth import sessions as auth_sessions

    await auth_sessions.revoke_other_sessions(db, operator_id, keep_session_id=None)
    audit.record(db, "admin.operator_suspended", actor_id=admin.id, subject_id=operator_id)
    await db.commit()
    last_seen = await db.scalar(select(func.max(Session.last_seen_at)).where(Session.user_id == operator_id))
    return _operator_row(operator, last_seen)


@router.post("/operators/{operator_id}/restore", response_model=schemas.OperatorRow)
async def restore_operator(operator_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    operator = await db.get(User, operator_id)
    if operator is None or operator.role != Role.admin:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Operator not found")
    operator.suspended_at = None
    operator.suspension_scopes = []
    operator.suspension_reason = None
    audit.record(db, "admin.operator_restored", actor_id=admin.id, subject_id=operator_id)
    await db.commit()
    last_seen = await db.scalar(select(func.max(Session.last_seen_at)).where(Session.user_id == operator_id))
    return _operator_row(operator, last_seen)


# --- trust rules (read-only proxy) and random audits ------------------------------


@router.get("/trust/rules")
async def trust_rules(admin: User = Depends(require_admin), client: httpx.AsyncClient = Depends(get_internal_client)):
    """A read-only proxy onto Intelligence's own `/internal/trust/rules` —
    the thresholds themselves are Intelligence's domain (see decision
    register); versioned draft/activate editing (the row's `POST`/
    `.../activate`) isn't built here, since that would mean this module
    writing into Intelligence's own tables rather than calling its
    contract."""
    resp = await client.get("/internal/trust/rules")
    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, "Could not reach the trust engine.")
    return resp.json()


@router.post("/submissions/{submission_id}/trust/review", status_code=status.HTTP_201_CREATED)
async def submit_trust_review(
    submission_id: uuid.UUID, payload: schemas.TrustReviewRequest, admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db), client: httpx.AsyncClient = Depends(get_internal_client),
):
    """The generic label-capture route — for a random audit or an
    investigation that isn't clearing/confirming a flag (those go through
    `/trust/clear` and `/trust/confirm`, which also apply the accrual
    override this route deliberately doesn't)."""
    resp = await client.post(
        f"/internal/submissions/{submission_id}/trust/review",
        json={"outcome": payload.outcome, "source": payload.source, "reviewer_id": str(admin.id), "notes": payload.notes},
    )
    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, resp.json().get("detail") if resp.content else "Review failed")
    audit.record(db, "admin.trust_review_recorded", actor_id=admin.id, submission_id=submission_id, outcome=payload.outcome, source=payload.source)
    await db.commit()
    return resp.json()


# --- provider health -------------------------------------------------------------


@router.get("/providers", response_model=list[schemas.ProviderHealth])
async def provider_health(admin: User = Depends(require_admin)):
    """Configured/sandbox state only — no latency, quota, or circuit-state
    tracking exists yet (that needs a metrics/observability layer this
    pass doesn't add; see production-api-inventory.md's monitoring gap)."""
    settings = get_settings()
    from integrations.payments import get_provider as get_payment_provider
    from modules.auth.providers import REGISTRY as OAUTH_PROVIDERS

    provider = get_payment_provider()
    rows = [
        schemas.ProviderHealth(name=provider.name, kind="payment", configured=True, sandbox=provider.sandbox),
        schemas.ProviderHealth(name=settings.email_backend, kind="email", configured=True, sandbox=settings.email_backend != "smtp"),
        schemas.ProviderHealth(name=settings.storage_backend, kind="storage", configured=True, sandbox=settings.storage_backend != "r2"),
        schemas.ProviderHealth(name="google", kind="identity", configured=bool(settings.google_client_id)),
    ]
    for platform in OAUTH_PROVIDERS:
        creds = (
            getattr(settings, f"{platform}_client_key", None)
            or getattr(settings, f"{platform}_app_id", None)
            or getattr(settings, f"{platform}_client_id", None)
        )
        rows.append(schemas.ProviderHealth(name=platform, kind="social", configured=bool(creds)))
    return rows


# --- refunds, payout reconciliation, jobs, ledger export (scattered P1s) --------


@router.get("/refunds", response_model=list[schemas.AdminLedgerRow])
async def list_refunds_admin(
    status_filter: refund_models.RefundStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(refund_models.Refund)
    if status_filter:
        query = query.where(refund_models.Refund.status == status_filter)
    rows = await db.scalars(query.order_by(refund_models.Refund.created_at.desc()).limit(limit).offset(offset))
    return [
        schemas.AdminLedgerRow(
            id=r.id, kind="refund", organisation_id=r.organisation_id, creator_id=None, campaign_id=r.campaign_id,
            amount=r.amount, status=r.status.value, provider=r.provider, provider_reference=r.provider_reference,
            reference=r.reference, created_at=r.created_at, settled_at=r.processed_at,
        )
        for r in rows
    ]


@router.post("/payouts/{payout_id}/reconcile", response_model=schemas.AdminPayoutRow)
async def reconcile_payout(payout_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Asks the provider for authoritative state on one payout right now,
    instead of waiting for the next sweep (`payouts.jobs.reconcile_tick`)."""
    payout = await _payout(db, payout_id)
    if payout.status not in (payout_models.PayoutStatus.pending, payout_models.PayoutStatus.processing):
        raise HTTPException(status.HTTP_409_CONFLICT, f"This payout is {payout.status.value}; nothing to reconcile.")
    changed = await payout_service.reconcile_one(db, payout)
    audit.record(db, "admin.payout_reconciled", actor_id=admin.id, subject_id=payout.creator_id, reference=payout.reference, changed=changed)
    await db.commit()
    await db.refresh(payout)
    user = await db.get(User, payout.creator_id)
    return schemas.AdminPayoutRow(
        id=payout.id, reference=payout.reference, status=payout.status.value, amount=payout.amount,
        creator_id=user.id, creator_email=user.email, creator_name=user.full_name, provider=payout.provider,
        provider_reference=payout.provider_reference, failure_reason=payout.failure_reason,
        initiated_at=payout.initiated_at, completed_at=payout.completed_at,
    )


@router.get("/jobs")
async def list_jobs(admin: User = Depends(require_admin)):
    """Only name and configured interval — no last-run/next-run/duration/
    processed-count/last-error tracking exists (the loop in `core.jobs`
    doesn't record any run history yet), so those fields from the
    inventory row aren't returned."""
    from core.jobs import registered

    return [{"name": j.name, "interval_seconds": j.interval_seconds} for j in registered()]


@router.post("/jobs/{job_name}/run", response_model=schemas.RunResult)
async def run_job(job_name: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Runs one allowlisted job immediately. No idempotency key is enforced
    here (unlike money-moving POSTs) — every registered job is already
    written to be safe to run twice (see `core.jobs`'s own docstring)."""
    from core.jobs import registered

    job = next((j for j in registered() if j.name == job_name), None)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No job named {job_name!r}.")
    audit.record(db, "admin.job_run", actor_id=admin.id, job_name=job_name)
    await db.commit()
    await job.run()
    return schemas.RunResult(processed=0)  # the wrapped job functions don't report a count back
