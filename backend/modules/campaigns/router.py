import csv
import io
import uuid
from dataclasses import asdict
from datetime import timedelta
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.deps import get_db
from core.internal_client import get_internal_client
from core.money import ZERO
from core.platforms import Platform
from modules.audit import service as audit
from modules.auth.deps import get_current_user, get_verified_user
from modules.auth.models import Role, SocialAccount, User
from modules.creators.models import CreatorProfile
from modules.earnings.models import EarningAccount, EarningEntry
from modules.funding import models as funding_models
from modules.funding import service as funding_service
from modules.organisations.models import OrganisationProfile
from modules.submissions.models import Submission, SubmissionStatus, VerificationStatus
from modules.uploads.router import owned_upload

from . import models, pool, schemas, service

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


async def _load(ref: str, db: AsyncSession) -> models.Campaign:
    campaign = await service.resolve(db, ref)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    return campaign


async def _out(db: AsyncSession, campaign: models.Campaign, user: User) -> schemas.CampaignOut:
    return (await service.build_outs(db, [campaign], user))[0]


# --- create / list / read ------------------------------------------------------


@router.post("", response_model=schemas.CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: schemas.CampaignCreate,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != Role.organisation:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an event manager account can create a campaign")
    if payload.cover_image_upload_id:
        await owned_upload(db, payload.cover_image_upload_id, user.id, kinds=("image",))
    try:
        pot, expected_views = service.derive_budget(
            pot=payload.pot, expected_views=payload.expected_views, rate=payload.payout_rule.rate_per_1000_views
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    campaign = models.Campaign(
        event_manager_id=user.id,
        slug=await service.unique_slug(db, payload.title),
        title=payload.title,
        tagline=payload.tagline,
        description=payload.description,
        category=payload.category,
        source_link=payload.source_link,
        cover_image_upload_id=payload.cover_image_upload_id,
        expected_views=expected_views,
        pot_amount=pot,
        duration_days=payload.duration_days,
        platforms=[p.value for p in payload.platforms],
    )
    db.add(campaign)
    await db.flush()
    db.add(models.CampaignPayoutRule(campaign_id=campaign.id, **payload.payout_rule.model_dump()))
    for position, rule in enumerate(payload.rules):
        db.add(models.CampaignRule(campaign_id=campaign.id, kind=rule.kind, text=rule.text, position=position))
    audit.record(db, "campaign.created", actor_id=user.id, campaign_id=campaign.id, amount=pot)
    await db.commit()
    return await _out(db, await _load(str(campaign.id), db), user)


@router.get("", response_model=list[schemas.CampaignOut])
async def list_campaigns(
    status_filter: models.CampaignStatus | None = None,
    q: str | None = Query(None, max_length=80, description="Matches title, category or brand name"),
    category: str | None = Query(None, max_length=40),
    platform: Platform | None = None,
    feed: Literal["all", "for_you", "joined", "closing_soon", "open"] = "all",
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """An organisation sees its own campaigns in any status. Everyone else
    sees live ones (creators additionally: not ended). `feed` is the creator
    directory's tabs; the rest are filters any role can use."""
    query = (
        select(models.Campaign)
        .outerjoin(OrganisationProfile, OrganisationProfile.user_id == models.Campaign.event_manager_id)
        .options(selectinload(models.Campaign.payout_rule), selectinload(models.Campaign.rules))
    )

    if user.role == Role.organisation:
        query = query.where(models.Campaign.event_manager_id == user.id)
        if status_filter:
            query = query.where(models.Campaign.status == status_filter)
    else:
        query = query.where(models.Campaign.status == (status_filter or models.CampaignStatus.active))
        if user.role == Role.creator:
            query = query.where(or_(models.Campaign.ends_at.is_(None), models.Campaign.ends_at > service.now()))

    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            or_(
                models.Campaign.title.ilike(like),
                models.Campaign.tagline.ilike(like),
                models.Campaign.category.ilike(like),
                OrganisationProfile.name.ilike(like),
            )
        )
    if category:
        query = query.where(func.lower(models.Campaign.category) == category.strip().lower())
    if platform:
        query = query.where(models.Campaign.platforms.any(platform.value))

    order = models.Campaign.created_at.desc()
    if feed == "closing_soon":
        query = query.where(models.Campaign.ends_at <= service.now() + service.CLOSING_SOON)
        order = models.Campaign.ends_at.asc()
    elif feed == "joined" and user.role == Role.creator:
        query = query.where(
            models.Campaign.id.in_(
                select(Submission.campaign_id).where(
                    Submission.creator_id == user.id, Submission.status != SubmissionStatus.withdrawn
                )
            )
        )
    elif feed == "open" and user.role == Role.creator:
        query = query.where(
            models.Campaign.id.not_in(
                select(Submission.campaign_id).where(
                    Submission.creator_id == user.id, Submission.status != SubmissionStatus.withdrawn
                )
            )
        )
    elif feed == "for_you" and user.role == Role.creator:
        profile = await db.get(CreatorProfile, user.id)
        interests = [i.lower() for i in (profile.interests if profile else [])]
        if interests:
            query = query.where(func.lower(models.Campaign.category).in_(interests))

    campaigns = list(await db.scalars(query.order_by(order).limit(limit).offset(offset)))
    return await service.build_outs(db, campaigns, user)


@router.get("/{campaign_ref}", response_model=schemas.CampaignOut)
async def get_campaign(campaign_ref: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    campaign = await _load(campaign_ref, db)
    service.ensure_visible(campaign, user)
    return await _out(db, campaign, user)


@router.get("/{campaign_ref}/pool", response_model=schemas.PoolOut)
async def read_pool(
    campaign_ref: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_internal_client),
):
    """What share of the promised pot current submissions would take."""
    campaign = await _load(campaign_ref, db)
    service.ensure_visible(campaign, user)
    if campaign.payout_rule is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This campaign has no payout rule")

    rule = campaign.payout_rule
    size = float(campaign.pot_amount) or pool.pot_size(campaign.expected_views, rule.rate_per_1000_views)
    submission_ids = list(
        await db.scalars(
            select(Submission.id).where(
                Submission.campaign_id == campaign.id,
                Submission.status == SubmissionStatus.submitted,
            )
        )
    )
    obligations: list[float] = []
    for submission_id in submission_ids:
        views = await _latest_views(client, submission_id)
        obligations.append(
            pool.obligation(
                views,
                rate_per_1000_views=rule.rate_per_1000_views,
                min_views_threshold=rule.min_views_threshold,
                cap_amount=rule.cap_amount,
            )
        )
    summary = pool.summarize(size, obligations)
    return schemas.PoolOut(campaign_id=campaign.id, **asdict(summary))


async def _latest_views(client: httpx.AsyncClient, submission_id: uuid.UUID) -> int:
    try:
        resp = await client.get(f"/internal/submissions/{submission_id}/performance")
    except httpx.HTTPError:
        return 0
    if resp.status_code >= 400:
        return 0
    views = (resp.json().get("metrics") or {}).get("views")
    return int(views) if views is not None else 0


# --- edit (draft only) ----------------------------------------------------------


@router.patch("/{campaign_ref}", response_model=schemas.CampaignOut)
async def update_campaign(
    campaign_ref: str,
    payload: schemas.CampaignUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    campaign = await _load(campaign_ref, db)
    service.ensure_can_manage(campaign, user)
    service.ensure_editable(campaign, user)

    changes = payload.model_dump(exclude_unset=True)
    if "pot" in changes or "expected_views" in changes:
        if campaign.status != models.CampaignStatus.draft:
            raise HTTPException(status.HTTP_409_CONFLICT, "The pot can't change after funding has started.")
        rate = campaign.payout_rule.rate_per_1000_views if campaign.payout_rule else None
        if rate is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Set the payout rate before changing the budget.")
        try:
            campaign.pot_amount, campaign.expected_views = service.derive_budget(
                pot=changes.pop("pot", None), expected_views=changes.pop("expected_views", None), rate=rate
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    if changes.get("cover_image_upload_id"):
        await owned_upload(db, changes["cover_image_upload_id"], user.id, kinds=("image",))
    if "platforms" in changes:
        changes["platforms"] = [p.value if hasattr(p, "value") else p for p in changes["platforms"]]
    for field, value in changes.items():
        setattr(campaign, field, value)

    audit.record(db, "campaign.updated", actor_id=user.id, campaign_id=campaign.id, fields=sorted(payload.model_dump(exclude_unset=True)))
    await db.commit()
    return await _out(db, await _load(str(campaign.id), db), user)


@router.put("/{campaign_ref}/payout-rule", response_model=schemas.PayoutRuleOut)
async def set_payout_rule(
    campaign_ref: str,
    payload: schemas.PayoutRuleIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    campaign = await _load(campaign_ref, db)
    service.ensure_can_manage(campaign, user)
    service.ensure_editable(campaign, user)
    if campaign.status != models.CampaignStatus.draft:
        raise HTTPException(status.HTTP_409_CONFLICT, "The payout rule is locked once funding has started.")

    if campaign.payout_rule:
        for field, value in payload.model_dump().items():
            setattr(campaign.payout_rule, field, value)
    else:
        db.add(models.CampaignPayoutRule(campaign_id=campaign.id, **payload.model_dump()))
    if campaign.pot_amount > 0:
        # The pot is the promise; a new rate changes how many views it buys.
        campaign.pot_amount, campaign.expected_views = service.derive_budget(
            pot=float(campaign.pot_amount), expected_views=None, rate=payload.rate_per_1000_views
        )
    await db.commit()
    return (await _load(str(campaign.id), db)).payout_rule


@router.get("/{campaign_ref}/rules", response_model=list[schemas.RuleOut])
async def get_rules(campaign_ref: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    campaign = await _load(campaign_ref, db)
    service.ensure_visible(campaign, user)
    return list(campaign.rules)


@router.put("/{campaign_ref}/rules", response_model=list[schemas.RuleOut])
async def replace_rules(
    campaign_ref: str,
    payload: schemas.RulesReplace,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replaces the whole brief. Sent as one list because that is how the
    builder edits it (add, remove, reorder) — no partial-update races."""
    campaign = await _load(campaign_ref, db)
    service.ensure_can_manage(campaign, user)
    service.ensure_editable(campaign, user)
    if campaign.status != models.CampaignStatus.draft:
        raise HTTPException(status.HTTP_409_CONFLICT, "The brief is locked once funding has started.")

    campaign.rules.clear()
    await db.flush()
    for position, rule in enumerate(payload.rules):
        campaign.rules.append(models.CampaignRule(kind=rule.kind, text=rule.text, position=position))
    audit.record(db, "campaign.rules_replaced", actor_id=user.id, campaign_id=campaign.id, count=len(payload.rules))
    await db.commit()
    return list((await _load(str(campaign.id), db)).rules)


# --- lifecycle ---------------------------------------------------------------------


@router.post("/{campaign_ref}/activate", response_model=schemas.CampaignOut)
async def activate_campaign(
    campaign_ref: str,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Opens a campaign whose pot is confirmed. There is no way to open one
    that isn't: an unfunded campaign would promise creators money that
    isn't there."""
    campaign = await _load(campaign_ref, db)
    service.ensure_can_manage(campaign, user)
    if campaign.status in (models.CampaignStatus.active, models.CampaignStatus.closed):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Campaign is already {campaign.status.value}")
    order = await funding_service.latest_order(db, campaign.id)
    if order is None or order.status != funding_models.FundingStatus.confirmed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Fund this campaign first — its pot isn't confirmed yet.")

    await funding_service.open_campaign(db, campaign, actor_id=user.id)
    await db.commit()
    return await _out(db, await _load(str(campaign.id), db), user)


@router.post("/{campaign_ref}/pause", response_model=schemas.CampaignOut)
async def pause_entries(campaign_ref: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Stop new submissions. Clips already in keep earning."""
    campaign = await _load(campaign_ref, db)
    service.ensure_can_manage(campaign, user)
    if campaign.status != models.CampaignStatus.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a live campaign can be paused.")
    campaign.accepting_entries = False
    audit.record(db, "campaign.paused", actor_id=user.id, campaign_id=campaign.id)
    await db.commit()
    return await _out(db, await _load(str(campaign.id), db), user)


@router.post("/{campaign_ref}/resume", response_model=schemas.CampaignOut)
async def resume_entries(campaign_ref: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    campaign = await _load(campaign_ref, db)
    service.ensure_can_manage(campaign, user)
    if campaign.status != models.CampaignStatus.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a live campaign can be resumed.")
    campaign.accepting_entries = True
    audit.record(db, "campaign.resumed", actor_id=user.id, campaign_id=campaign.id)
    await db.commit()
    return await _out(db, await _load(str(campaign.id), db), user)


@router.post("/{campaign_ref}/close", response_model=schemas.CampaignOut)
async def close_campaign(
    campaign_ref: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_internal_client),
):
    campaign = await _load(campaign_ref, db)
    service.ensure_can_manage(campaign, user)
    if campaign.status == models.CampaignStatus.closed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Campaign is already closed")
    if campaign.status == models.CampaignStatus.pending_funding:
        order = await funding_service.latest_order(db, campaign.id)
        if order and order.status == funding_models.FundingStatus.awaiting_confirmation:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Payment is awaiting confirmation; it can't be closed until that resolves."
            )

    reason = models.CloseReason.admin if user.role == Role.admin else models.CloseReason.manual
    await service.close_campaign(db, campaign, reason, actor_id=user.id, client=client)
    return await _out(db, await _load(str(campaign.id), db), user)


# --- the brand's live view -------------------------------------------------------------


@router.get("/{campaign_ref}/stats", response_model=schemas.CampaignStats)
async def campaign_stats(campaign_ref: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    campaign = await _load(campaign_ref, db)
    service.ensure_can_manage(campaign, user)

    spent = (await service.spent_by_campaign(db, [campaign.id])).get(campaign.id, ZERO)
    counts = (await service.counts_by_campaign(db, [campaign.id]))[campaign.id]
    views = (await service.views_by_campaign(db, [campaign.id])).get(campaign.id, 0)
    since = service.now() - timedelta(hours=24)
    views_24h = await db.scalar(
        select(func.coalesce(func.sum(EarningEntry.billable_views), 0)).where(
            EarningEntry.campaign_id == campaign.id, EarningEntry.accrued_at >= since
        )
    )
    last_reading = await db.scalar(
        select(func.max(EarningAccount.last_settled_at)).where(EarningAccount.campaign_id == campaign.id)
    )
    remaining = max(campaign.pot_amount - spent, ZERO)
    percent_remaining = float(remaining / campaign.pot_amount * 100) if campaign.pot_amount > 0 else 0.0
    return schemas.CampaignStats(
        campaign_id=campaign.id,
        phase=service.PHASE[campaign.status],
        accepting_entries=campaign.accepting_entries,
        pot=campaign.pot_amount,
        spent=spent,
        remaining=remaining,
        percent_remaining=round(percent_remaining, 2),
        verified_views=views,
        views_last_24h=int(views_24h or 0),
        submissions=counts.submissions,
        approved=counts.approved,
        review=counts.review,
        checking=counts.checking,
        rejected=counts.rejected,
        time_left=service.time_left(campaign.ends_at) if campaign.status == models.CampaignStatus.active else None,
        last_reading_at=last_reading,
    )


def _csv_safe(value) -> str:
    """Spreadsheet formula injection: a cell that starts with = + - or @ is
    executed by Excel/Sheets. Creator-controlled text (names, URLs) reaches
    this report, so such cells are prefixed with a quote."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


async def _submission_rows(db: AsyncSession, campaign_id: uuid.UUID, limit: int | None) -> list[schemas.CampaignSubmissionRow]:
    query = (
        select(Submission, User, EarningAccount)
        .join(User, User.id == Submission.creator_id)
        .outerjoin(EarningAccount, EarningAccount.submission_id == Submission.id)
        .where(Submission.campaign_id == campaign_id)
        .order_by(func.coalesce(EarningAccount.accrued_amount, 0).desc(), Submission.created_at.desc())
    )
    if limit:
        query = query.limit(limit)
    rows = (await db.execute(query)).all()

    creator_ids = {sub.creator_id for sub, _, _ in rows}
    profiles = {
        p.user_id: p for p in await db.scalars(select(CreatorProfile).where(CreatorProfile.user_id.in_(creator_ids)))
    } if creator_ids else {}
    handles: dict[tuple[uuid.UUID, str], str | None] = {}
    if creator_ids:
        for acct in await db.scalars(select(SocialAccount).where(SocialAccount.user_id.in_(creator_ids))):
            handles[(acct.user_id, acct.platform.value)] = acct.handle

    out = []
    for sub, creator, account in rows:
        if sub.status == SubmissionStatus.withdrawn:
            state = "Withdrawn"
        elif sub.status == SubmissionStatus.rejected or sub.verification_status == VerificationStatus.rejected:
            state = "Rejected"
        elif sub.verification_status == VerificationStatus.approved:
            state = "Earning"
        elif sub.verification_status in (VerificationStatus.needs_review, VerificationStatus.appealed):
            state = "Review"
        else:
            state = "Checking"
        profile = profiles.get(sub.creator_id)
        out.append(
            schemas.CampaignSubmissionRow(
                id=sub.id,
                creator_id=sub.creator_id,
                creator_name=(profile.display_name if profile else creator.full_name),
                creator_handle=handles.get((sub.creator_id, sub.platform)),
                title=sub.title,
                platform=sub.platform,
                url=sub.url,
                verified_views=int(account.cumulative_views) if account else 0,
                earned=account.accrued_amount if account else ZERO,
                state=state,
                submitted_at=sub.created_at,
            )
        )
    return out


@router.get("/{campaign_ref}/submissions", response_model=list[schemas.CampaignSubmissionRow])
async def campaign_submissions(
    campaign_ref: str,
    limit: int = Query(20, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submissions with verified views and earnings — the live campaign's
    "Recent submissions" table."""
    campaign = await _load(campaign_ref, db)
    service.ensure_can_manage(campaign, user)
    return await _submission_rows(db, campaign.id, limit)


@router.get("/{campaign_ref}/report")
async def campaign_report(campaign_ref: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """CSV of every submission, for the brand's own records."""
    campaign = await _load(campaign_ref, db)
    service.ensure_can_manage(campaign, user)
    rows = await _submission_rows(db, campaign.id, None)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["submission_id", "creator", "handle", "platform", "url", "state", "verified_views", "earned", "submitted_at"])
    for r in rows:
        writer.writerow(
            [_csv_safe(v) for v in (r.id, r.creator_name, r.creator_handle, r.platform, r.url, r.state, r.verified_views, f"{r.earned:.2f}", r.submitted_at.isoformat())]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{campaign.slug}-report.csv"'},
    )
