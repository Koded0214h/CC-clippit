"""Campaign logic that more than one route (or a scheduled job) needs.

Everything that turns rows into the shapes the screens show lives here, in
batch form: a list of 30 campaigns costs a handful of queries, not 30 × N.
"""

from __future__ import annotations

import re
import secrets
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.money import ZERO, quantize, to_decimal
from modules.audit import service as audit
from modules.auth.models import Platform as AuthPlatform
from modules.auth.models import Role, SocialAccount, User
from modules.earnings.models import EarningAccount, EarningEntry
from modules.organisations.models import OrganisationProfile
from modules.submissions.models import Submission, SubmissionStatus, VerificationStatus
from modules.uploads.models import Upload
from core.storage import get_storage

from . import models, schemas

CLOSING_SOON = timedelta(hours=72)

PHASE = {
    models.CampaignStatus.draft: "Draft",
    models.CampaignStatus.pending_funding: "Funding",
    models.CampaignStatus.active: "Live",
    models.CampaignStatus.closed: "Completed",
}


def now() -> datetime:
    return datetime.now(timezone.utc)


# --- identifiers ------------------------------------------------------------


def slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text[:60].strip("-") or "campaign"


async def unique_slug(db: AsyncSession, title: str) -> str:
    base = slugify(title)
    candidate = base
    while await db.scalar(select(models.Campaign.id).where(models.Campaign.slug == candidate)):
        candidate = f"{base}-{secrets.token_hex(2)}"
    return candidate


async def create_campaign(db: AsyncSession, owner: User, payload: schemas.CampaignCreate) -> models.Campaign:
    """The one place a `Campaign` row gets created — used by `POST
    /campaigns` directly and by `POST /campaign-drafts/{id}/finalize`
    (which re-validates its accumulated draft as this same
    `CampaignCreate` shape first). Does not commit; the caller decides
    the transaction boundary."""
    pot, expected_views = derive_budget(
        pot=payload.pot, expected_views=payload.expected_views, rate=payload.payout_rule.rate_per_1000_views
    )
    campaign = models.Campaign(
        event_manager_id=owner.id,
        slug=await unique_slug(db, payload.title),
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
    audit.record(db, "campaign.created", actor_id=owner.id, campaign_id=campaign.id, amount=pot)
    return campaign


async def resolve(db: AsyncSession, ref: str) -> models.Campaign | None:
    """A campaign by UUID or by slug — the frontend routes on slugs, every
    other caller has ids."""
    try:
        key = models.Campaign.id == uuid.UUID(ref)
    except ValueError:
        key = models.Campaign.slug == ref
    from sqlalchemy.orm import selectinload

    return await db.scalar(
        select(models.Campaign)
        .options(selectinload(models.Campaign.payout_rule), selectinload(models.Campaign.rules))
        .where(key)
    )


# --- the budget identity -----------------------------------------------------


def derive_budget(*, pot: float | None, expected_views: int | None, rate: float) -> tuple[Decimal, int]:
    """(pot, expected_views) from whichever the brand supplied.

    A pot of ₦500,000 at ₦500 per 1,000 views is 1,000,000 views. Partial
    thousands are never billed, so views are floored, never rounded up.
    """
    rate_d = to_decimal(rate)
    if pot is not None:
        pot_d = quantize(to_decimal(pot))
        views = int((pot_d / rate_d * 1000).to_integral_value(rounding="ROUND_FLOOR"))
        if views < 1:
            raise ValueError("That pot is too small to buy even one view at this rate.")
        return pot_d, views
    assert expected_views is not None
    return quantize(to_decimal(expected_views) / 1000 * rate_d), expected_views


# --- batch aggregates ---------------------------------------------------------


async def spent_by_campaign(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    if not ids:
        return {}
    rows = await db.execute(
        select(EarningEntry.campaign_id, func.coalesce(func.sum(EarningEntry.amount), 0))
        .where(EarningEntry.campaign_id.in_(ids))
        .group_by(EarningEntry.campaign_id)
    )
    return {cid: to_decimal(total) for cid, total in rows}


@dataclass
class Counts:
    submissions: int = 0
    approved: int = 0
    review: int = 0
    checking: int = 0
    rejected: int = 0


async def counts_by_campaign(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, Counts]:
    out: dict[uuid.UUID, Counts] = defaultdict(Counts)
    if not ids:
        return out
    rows = await db.execute(
        select(Submission.campaign_id, Submission.status, Submission.verification_status, func.count())
        .where(Submission.campaign_id.in_(ids), Submission.status != SubmissionStatus.withdrawn)
        .group_by(Submission.campaign_id, Submission.status, Submission.verification_status)
    )
    for cid, link_status, verdict, n in rows:
        c = out[cid]
        c.submissions += n
        if link_status == SubmissionStatus.rejected or verdict == VerificationStatus.rejected:
            c.rejected += n
        elif verdict == VerificationStatus.approved:
            c.approved += n
        elif verdict in (VerificationStatus.needs_review, VerificationStatus.appealed):
            c.review += n
        else:
            c.checking += n
    return out


async def views_by_campaign(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not ids:
        return {}
    rows = await db.execute(
        select(EarningAccount.campaign_id, func.coalesce(func.sum(EarningAccount.cumulative_views), 0))
        .where(EarningAccount.campaign_id.in_(ids))
        .group_by(EarningAccount.campaign_id)
    )
    return {cid: int(total) for cid, total in rows}


async def brands(db: AsyncSession, org_ids: set[uuid.UUID]) -> dict[uuid.UUID, schemas.BrandOut]:
    if not org_ids:
        return {}
    storage = get_storage()
    profiles = {
        p.user_id: p
        for p in await db.scalars(select(OrganisationProfile).where(OrganisationProfile.user_id.in_(org_ids)))
    }
    upload_ids = {p.photo_upload_id for p in profiles.values() if p.photo_upload_id}
    keys = (
        {u.id: u.key for u in await db.scalars(select(Upload).where(Upload.id.in_(upload_ids)))}
        if upload_ids
        else {}
    )
    users = {u.id: u for u in await db.scalars(select(User).where(User.id.in_(org_ids)))}
    out: dict[uuid.UUID, schemas.BrandOut] = {}
    for org_id in org_ids:
        profile = profiles.get(org_id)
        user = users.get(org_id)
        out[org_id] = schemas.BrandOut(
            id=org_id,
            name=(profile.name if profile else (user.full_name if user else "Organisation")),
            photo_url=storage.url_for(keys[profile.photo_upload_id]) if profile and profile.photo_upload_id in keys else None,
            verified=bool(profile and profile.business_verified),
        )
    return out


async def cover_urls(db: AsyncSession, campaigns: list[models.Campaign]) -> dict[uuid.UUID, str]:
    ids = {c.cover_image_upload_id for c in campaigns if c.cover_image_upload_id}
    if not ids:
        return {}
    storage = get_storage()
    return {u.id: storage.url_for(u.key) for u in await db.scalars(select(Upload).where(Upload.id.in_(ids)))}


async def joined_campaigns(db: AsyncSession, creator_id: uuid.UUID, ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """"Joined" is true from an explicit `CampaignMembership`, or — for
    creators who submitted before that existed, or resubmit straight from
    the feed — from having a live submission either way."""
    if not ids:
        return set()
    from_membership = await db.scalars(
        select(models.CampaignMembership.campaign_id).where(
            models.CampaignMembership.creator_id == creator_id,
            models.CampaignMembership.campaign_id.in_(ids),
            models.CampaignMembership.left_at.is_(None),
        )
    )
    from_submission = await db.scalars(
        select(Submission.campaign_id).where(
            Submission.creator_id == creator_id,
            Submission.campaign_id.in_(ids),
            Submission.status != SubmissionStatus.withdrawn,
        )
    )
    return set(from_membership) | set(from_submission)


# --- membership ---------------------------------------------------------------


class MembershipError(Exception):
    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def active_membership(
    db: AsyncSession, campaign_id: uuid.UUID, creator_id: uuid.UUID
) -> models.CampaignMembership | None:
    return await db.scalar(
        select(models.CampaignMembership).where(
            models.CampaignMembership.campaign_id == campaign_id,
            models.CampaignMembership.creator_id == creator_id,
            models.CampaignMembership.left_at.is_(None),
        )
    )


async def join_campaign(
    db: AsyncSession, campaign: models.Campaign, creator: User
) -> models.CampaignMembership:
    """Idempotent: joining twice returns the existing membership rather
    than erroring, since the frontend can't always tell whether a click
    landed the first time."""
    if not is_open_for_entries(campaign):
        raise MembershipError("This campaign isn't accepting new creators right now.")
    existing = await active_membership(db, campaign.id, creator.id)
    if existing:
        return existing

    has_account = await db.scalar(
        select(SocialAccount.id).where(
            SocialAccount.user_id == creator.id,
            SocialAccount.platform.in_([AuthPlatform(p) for p in campaign.platforms]),
        )
    )
    if not has_account:
        raise MembershipError(
            "Connect one of this campaign's platforms from your profile before joining.", status_code=409
        )

    membership = models.CampaignMembership(campaign_id=campaign.id, creator_id=creator.id)
    db.add(membership)
    await db.flush()
    audit.record(db, "campaign.joined", actor_id=creator.id, campaign_id=campaign.id)
    return membership


async def leave_campaign(db: AsyncSession, campaign: models.Campaign, creator: User) -> models.CampaignMembership:
    membership = await active_membership(db, campaign.id, creator.id)
    if membership is None:
        raise MembershipError("You haven't joined this campaign.", status_code=404)
    has_accepted = await db.scalar(
        select(Submission.id).where(
            Submission.campaign_id == campaign.id,
            Submission.creator_id == creator.id,
            Submission.status == SubmissionStatus.submitted,
            Submission.verification_status == VerificationStatus.approved,
        )
    )
    if has_accepted:
        raise MembershipError("You can't leave after a clip has been accepted — withdraw the clip instead.")
    membership.left_at = now()
    audit.record(db, "campaign.left", actor_id=creator.id, campaign_id=campaign.id)
    return membership


# --- shaping -----------------------------------------------------------------


def time_left(ends_at: datetime | None, at: datetime | None = None) -> schemas.TimeLeft | None:
    if ends_at is None:
        return None
    remaining = ends_at - (at or now())
    if remaining.total_seconds() <= 0:
        return schemas.TimeLeft(days=0, hours=0, ended=True)
    return schemas.TimeLeft(days=remaining.days, hours=remaining.seconds // 3600, ended=False)


def feed_status(campaign: models.Campaign, joined: bool, at: datetime | None = None) -> str:
    if joined:
        return "Joined"
    left = (campaign.ends_at - (at or now())) if campaign.ends_at else None
    if left is not None and left <= CLOSING_SOON:
        return "Closing soon"
    return "Open"


async def build_outs(
    db: AsyncSession,
    campaigns: list[models.Campaign],
    viewer: User,
) -> list[schemas.CampaignOut]:
    """Full campaign cards for a list. Metrics are attached only for the
    campaign's own organisation (and admin); a creator gets `feed_status`
    and `joined` instead."""
    ids = [c.id for c in campaigns]
    spent = await spent_by_campaign(db, ids)
    brand_map = await brands(db, {c.event_manager_id for c in campaigns})
    covers = await cover_urls(db, campaigns)
    joined = await joined_campaigns(db, viewer.id, ids) if viewer.role == Role.creator else set()

    owned = [c.id for c in campaigns if viewer.role == Role.admin or c.event_manager_id == viewer.id]
    counts = await counts_by_campaign(db, owned)
    views = await views_by_campaign(db, owned)

    at = now()
    outs: list[schemas.CampaignOut] = []
    for c in campaigns:
        spent_c = spent.get(c.id, ZERO)
        out = schemas.CampaignOut(
            id=c.id,
            slug=c.slug,
            event_manager_id=c.event_manager_id,
            brand=brand_map.get(c.event_manager_id),
            title=c.title,
            tagline=c.tagline,
            description=c.description,
            category=c.category,
            source_link=c.source_link,
            cover_image_url=covers.get(c.cover_image_upload_id) if c.cover_image_upload_id else None,
            expected_views=c.expected_views,
            platforms=c.platforms,
            status=c.status,
            phase=PHASE[c.status],
            accepting_entries=c.accepting_entries,
            duration_days=c.duration_days,
            ends_at=c.ends_at,
            time_left=time_left(c.ends_at, at) if c.status == models.CampaignStatus.active else None,
            pot=c.pot_amount,
            spent=spent_c,
            remaining=max(c.pot_amount - spent_c, ZERO),
            payout_rule=c.payout_rule,
            rules=list(c.rules),
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        if viewer.role == Role.creator:
            out.joined = c.id in joined
            out.feed_status = feed_status(c, c.id in joined, at)
        if c.id in owned:
            n = counts.get(c.id, Counts())
            out.metrics = schemas.CampaignMetrics(
                verified_views=views.get(c.id, 0),
                submissions=n.submissions,
                approved=n.approved,
                review=n.review,
                checking=n.checking,
                rejected=n.rejected,
                earned=spent_c,
            )
        outs.append(out)
    return outs


# --- lifecycle ---------------------------------------------------------------


async def stop_tracking(client: httpx.AsyncClient, submission_ids: list[uuid.UUID]) -> None:
    """Tell Intelligence to stop polling (decision D17). Best effort: its own
    age cap eventually stops an unreachable one, and money is unaffected."""
    for submission_id in submission_ids:
        try:
            await client.post(f"/internal/submissions/{submission_id}/tracking/stop")
        except httpx.HTTPError:
            pass


async def close_campaign(
    db: AsyncSession,
    campaign: models.Campaign,
    reason: models.CloseReason,
    *,
    actor_id: uuid.UUID | None,
    client: httpx.AsyncClient | None = None,
) -> None:
    """Closes the campaign and stops tracking its submissions. New entries
    stop immediately; accruals already earned stay payable."""
    if campaign.status == models.CampaignStatus.closed:
        return
    campaign.status = models.CampaignStatus.closed
    campaign.closed_at = now()
    campaign.close_reason = reason
    campaign.accepting_entries = False
    audit.record(db, "campaign.closed", actor_id=actor_id, campaign_id=campaign.id, reason=reason.value)
    submission_ids = list(await db.scalars(select(Submission.id).where(Submission.campaign_id == campaign.id)))
    await db.commit()
    if client is not None:
        await stop_tracking(client, submission_ids)


async def close_due_campaigns(db: AsyncSession, client: httpx.AsyncClient | None = None) -> int:
    """Closes campaigns past their deadline or with an empty pot. Idempotent —
    a campaign already closed is skipped — and safe to run at any cadence."""
    from sqlalchemy.orm import selectinload

    active = list(
        await db.scalars(
            select(models.Campaign)
            .options(selectinload(models.Campaign.payout_rule))
            .where(models.Campaign.status == models.CampaignStatus.active)
        )
    )
    spent = await spent_by_campaign(db, [c.id for c in active])
    closed = 0
    for c in active:
        if c.ends_at is not None and c.ends_at <= now():
            reason = models.CloseReason.deadline
        elif c.pot_amount > 0 and spent.get(c.id, ZERO) >= c.pot_amount:
            reason = models.CloseReason.pot_empty
        else:
            continue
        await close_campaign(db, c, reason, actor_id=None, client=client)
        closed += 1
    return closed


def is_open_for_entries(campaign: models.Campaign, at: datetime | None = None) -> bool:
    if campaign.status != models.CampaignStatus.active or not campaign.accepting_entries:
        return False
    return campaign.ends_at is None or campaign.ends_at > (at or now())


# --- campaign studio drafts ----------------------------------------------------


def draft_blockers(answers: dict) -> dict[str, str]:
    """What `finalize` would still refuse on — computed without raising, so
    `GET`/`PATCH` can show the builder exactly which screen is incomplete."""
    blockers: dict[str, str] = {}
    if not (answers.get("title") or "").strip():
        blockers["title"] = "Add a campaign title."
    if not (answers.get("description") or "").strip():
        blockers["description"] = "Add a brief description."
    if not answers.get("platforms"):
        blockers["platforms"] = "Choose at least one platform."
    payout_rule = answers.get("payout_rule") or {}
    if not payout_rule.get("rate_per_1000_views"):
        blockers["payout_rule"] = "Set a rate per 1,000 views."
    if not answers.get("pot") and not answers.get("expected_views"):
        blockers["budget"] = "Set a pot or an expected-views target."
    return blockers


async def finalize_draft(db: AsyncSession, draft: models.CampaignDraft, owner: User) -> models.Campaign:
    if draft.finalized_campaign_id is not None:
        campaign = await db.get(models.Campaign, draft.finalized_campaign_id)
        if campaign is not None:
            return campaign  # idempotent: already finalized
    blockers = draft_blockers(draft.draft_answers)
    if blockers:
        raise ValueError("; ".join(blockers.values()))
    try:
        payload = schemas.CampaignCreate.model_validate(draft.draft_answers)
    except Exception as exc:  # pydantic ValidationError
        raise ValueError(str(exc)) from exc
    campaign = await create_campaign(db, owner, payload)
    await db.flush()
    draft.finalized_campaign_id = campaign.id
    return campaign


# --- access rules ------------------------------------------------------------


def ensure_can_manage(campaign: models.Campaign, user: User) -> None:
    if user.role == Role.admin:
        return
    if campaign.event_manager_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the campaign's owner or an admin can do this")


def ensure_visible(campaign: models.Campaign, user: User) -> None:
    """Drafts (and campaigns waiting on funding) are the brand's working
    copy: visible only to its owner and admin, and a 404 — not a 403 — for
    everyone else so their existence isn't confirmed."""
    unlisted = campaign.status in (models.CampaignStatus.draft, models.CampaignStatus.pending_funding)
    if unlisted and user.role != Role.admin and campaign.event_manager_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")


def ensure_editable(campaign: models.Campaign, user: User) -> None:
    """Terms change only before funding; admin may correct a live campaign."""
    if campaign.status != models.CampaignStatus.draft and user.role != Role.admin:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Terms are locked once a campaign is sent for funding. Cancel the funding order to edit.",
        )
