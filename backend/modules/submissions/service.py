"""Submission verdicts and the way they are presented.

Every state change here is one function that (1) checks the transition is
legal, (2) writes the change, (3) records an audit event and (4) notifies the
person waiting — in the caller's transaction, so the verdict, its audit row
and its notification are saved together or not at all.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.storage import get_storage
from modules.audit import service as audit
from modules.auth.models import User
from modules.campaigns.models import Campaign
from modules.campaigns.service import brands
from modules.earnings.models import EarningAccount
from modules.notifications.service import notify
from modules.uploads.models import Upload

from . import models, schemas
from .verification import get_verifier


class TransitionError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- running the verifier ------------------------------------------------------


async def run_verification(db: AsyncSession, submission: models.Submission, campaign: Campaign) -> None:
    """Asks the configured verifier and stores its verdicts. Called once,
    right after Intelligence accepts the link."""
    rules = list(campaign.rules)
    outcome = await get_verifier().verify(submission=submission, campaign=campaign, rules=rules)

    for position, check in enumerate(outcome.checks):
        db.add(
            models.SubmissionRequirementResult(
                submission_id=submission.id,
                rule_id=check.rule.id,
                kind=check.rule.kind.value,
                text=check.rule.text,
                position=position,
                verdict=check.verdict,
                note=check.note,
            )
        )
    submission.verification_status = outcome.status
    submission.verification_confidence = outcome.confidence
    submission.verification_summary = outcome.summary
    if outcome.status in (models.VerificationStatus.approved, models.VerificationStatus.rejected):
        submission.verdict_at = _now()
    audit.record(
        db, "submission.verified", submission_id=submission.id, campaign_id=campaign.id,
        status=outcome.status.value, automated=True,
    )
    if outcome.status == models.VerificationStatus.needs_review:
        await notify(
            db,
            campaign.event_manager_id,
            "review_needed",
            "A clip needs your review",
            f"A new submission to {campaign.title} is waiting for a decision. It doesn't earn until you decide.",
            link=f"/brand/reviews/{submission.id}",
        )


# --- decisions -----------------------------------------------------------------------

_REVIEWABLE = (models.VerificationStatus.needs_review, models.VerificationStatus.appealed)


async def _results(db: AsyncSession, submission_id: uuid.UUID) -> list[models.SubmissionRequirementResult]:
    return list(
        await db.scalars(
            select(models.SubmissionRequirementResult)
            .where(models.SubmissionRequirementResult.submission_id == submission_id)
            .order_by(models.SubmissionRequirementResult.position)
        )
    )


async def _open_appeal(db: AsyncSession, submission_id: uuid.UUID) -> models.SubmissionAppeal | None:
    return await db.scalar(
        select(models.SubmissionAppeal).where(
            models.SubmissionAppeal.submission_id == submission_id,
            models.SubmissionAppeal.status == models.AppealStatus.open,
        )
    )


async def approve(
    db: AsyncSession, submission: models.Submission, campaign: Campaign, decider: User, note: str | None = None
) -> None:
    if submission.verification_status not in _REVIEWABLE:
        raise TransitionError(f"This submission is {submission.verification_status.value}; there's nothing to approve.")
    appeal = await _open_appeal(db, submission.id)
    for result in await _results(db, submission.id):
        if result.verdict != models.RequirementVerdict.passed:
            result.verdict = models.RequirementVerdict.passed
            result.note = "Overturned on appeal." if appeal else "Approved by the brand."
    submission.verification_status = models.VerificationStatus.approved
    submission.verdict_at = _now()
    submission.verdict_by = decider.id
    submission.verification_summary = note or "Approved."
    if appeal:
        appeal.status = models.AppealStatus.overturned
        appeal.decided_by = decider.id
        appeal.decided_at = _now()
        appeal.decision_note = note
    audit.record(
        db, "submission.approved", actor_id=decider.id, submission_id=submission.id, campaign_id=campaign.id,
        appeal=bool(appeal),
    )
    await notify(
        db,
        submission.creator_id,
        "appeal_decision" if appeal else "submission_verdict",
        "Appeal upheld — your clip is approved" if appeal else "Your clip was approved",
        f"{submission.title or 'Your clip'} can now earn from verified views on {campaign.title}.",
        link=f"/dashboard/submissions/approved?id={submission.id}",
    )


async def request_correction(
    db: AsyncSession,
    submission: models.Submission,
    campaign: Campaign,
    decider: User,
    *,
    reason: str,
    requirement_id: uuid.UUID | None = None,
) -> None:
    if submission.verification_status not in _REVIEWABLE:
        raise TransitionError(f"This submission is {submission.verification_status.value}; there's nothing to correct.")
    results = await _results(db, submission.id)
    if requirement_id is not None:
        target = next((r for r in results if r.id == requirement_id), None)
        if target is None:
            raise TransitionError("That requirement isn't part of this submission.")
    else:
        target = next((r for r in results if r.verdict == models.RequirementVerdict.review), None)
    if target is not None:
        target.verdict = models.RequirementVerdict.failed
        target.note = reason

    appeal = await _open_appeal(db, submission.id)
    submission.verification_status = models.VerificationStatus.rejected
    submission.verdict_at = _now()
    submission.verdict_by = decider.id
    submission.verification_summary = reason
    if appeal:
        appeal.status = models.AppealStatus.upheld
        appeal.decided_by = decider.id
        appeal.decided_at = _now()
        appeal.decision_note = reason
    audit.record(
        db, "submission.correction_requested", actor_id=decider.id, submission_id=submission.id,
        campaign_id=campaign.id, appeal=bool(appeal),
    )
    await notify(
        db,
        submission.creator_id,
        "appeal_decision" if appeal else "submission_verdict",
        "Appeal reviewed — the original decision stands" if appeal else "Correction needed on your clip",
        reason,
        link=f"/dashboard/submissions/rejected?id={submission.id}",
    )


async def submit_appeal(
    db: AsyncSession,
    submission: models.Submission,
    campaign: Campaign,
    creator: User,
    *,
    reason: str,
    evidence_upload_id: uuid.UUID | None,
) -> models.SubmissionAppeal:
    if submission.verification_status != models.VerificationStatus.rejected:
        raise TransitionError("Only a rejected clip can be appealed.")
    if await _open_appeal(db, submission.id):
        raise TransitionError("You've already appealed this clip.")
    previous = await db.scalar(
        select(models.SubmissionAppeal.id).where(models.SubmissionAppeal.submission_id == submission.id)
    )
    if previous:
        # One appeal per verdict: a second attempt after an upheld decision
        # would just be asking the same question again.
        raise TransitionError("This clip has already been through an appeal.")

    appeal = models.SubmissionAppeal(
        submission_id=submission.id, creator_id=creator.id, reason=reason, evidence_upload_id=evidence_upload_id
    )
    db.add(appeal)
    submission.verification_status = models.VerificationStatus.appealed
    audit.record(db, "submission.appealed", actor_id=creator.id, submission_id=submission.id, campaign_id=campaign.id)
    await notify(
        db,
        campaign.event_manager_id,
        "review_needed",
        "A creator appealed a verdict",
        f"An appeal on {submission.title or 'a clip'} in {campaign.title} needs your decision.",
        link=f"/brand/reviews/{submission.id}",
    )
    await db.flush()
    return appeal


# --- presenting ----------------------------------------------------------------------


def _steps(sub: models.Submission, requirement_count: int, has_views: bool) -> list[schemas.VerificationStep]:
    vs = models.VerificationStatus
    ownership = (
        "failed" if sub.status == models.SubmissionStatus.rejected
        else "done" if sub.status == models.SubmissionStatus.submitted
        else "pending"
    )
    if sub.verification_status == vs.approved:
        brief = "done"
    elif sub.verification_status == vs.rejected:
        brief = "failed"
    else:
        brief = "active"
    noun = "requirement" if requirement_count == 1 else "requirements"
    return [
        schemas.VerificationStep(
            key="post_ownership", title="Post ownership",
            detail="Matched to the connected account" if ownership == "done" else "Matching the post to your account",
            state=ownership,
        ),
        schemas.VerificationStep(
            key="brief_requirements", title="Brief requirements",
            detail=f"Checking {requirement_count} {noun}" if requirement_count else "No requirements to check",
            state=brief,
        ),
        schemas.VerificationStep(
            key="trust_signals", title="Trust signals", detail="Looking for unusual activity",
            state="done" if sub.verification_status == vs.approved else "pending",
        ),
        schemas.VerificationStep(
            key="first_reading", title="First view reading",
            detail="First reading recorded" if has_views else "Queued after approval",
            state="done" if has_views else "pending",
        ),
    ]


async def shape(db: AsyncSession, submissions: list[models.Submission]) -> list[schemas.SubmissionOut]:
    """Presents submissions with their campaign and verdict — in batch, so a
    list of 50 is a handful of queries, not 50 × 5."""
    if not submissions:
        return []
    ids = [s.id for s in submissions]
    # Re-read them: a commit expires server-updated columns (updated_at), and
    # touching an expired attribute in async code is a hard error, not a lazy load.
    fresh = {
        s.id: s
        for s in await db.scalars(
            select(models.Submission).where(models.Submission.id.in_(ids)).execution_options(populate_existing=True)
        )
    }
    submissions = [fresh[i] for i in ids]
    storage = get_storage()

    campaigns = {
        c.id: c for c in await db.scalars(select(Campaign).where(Campaign.id.in_({s.campaign_id for s in submissions})))
    }
    brand_map = await brands(db, {c.event_manager_id for c in campaigns.values()})

    results: dict[uuid.UUID, list[models.SubmissionRequirementResult]] = defaultdict(list)
    for r in await db.scalars(
        select(models.SubmissionRequirementResult)
        .where(models.SubmissionRequirementResult.submission_id.in_(ids))
        .order_by(models.SubmissionRequirementResult.position)
    ):
        results[r.submission_id].append(r)

    appeals: dict[uuid.UUID, models.SubmissionAppeal] = {}
    for a in await db.scalars(
        select(models.SubmissionAppeal)
        .where(models.SubmissionAppeal.submission_id.in_(ids))
        .order_by(models.SubmissionAppeal.created_at)
    ):
        appeals[a.submission_id] = a  # the latest wins

    with_views = {
        row for row in await db.scalars(
            select(EarningAccount.submission_id).where(EarningAccount.submission_id.in_(ids), EarningAccount.cumulative_views > 0)
        )
    }

    upload_ids = {s.video_upload_id for s in submissions if s.video_upload_id} | {
        a.evidence_upload_id for a in appeals.values() if a.evidence_upload_id
    }
    urls = (
        {u.id: storage.url_for(u.key) for u in await db.scalars(select(Upload).where(Upload.id.in_(upload_ids)))}
        if upload_ids else {}
    )

    out: list[schemas.SubmissionOut] = []
    for s in submissions:
        c = campaigns.get(s.campaign_id)
        rs = results.get(s.id, [])
        failed = next((r for r in rs if r.verdict == models.RequirementVerdict.failed), None)
        appeal = appeals.get(s.id)
        verification = schemas.VerificationOut(
            status=s.verification_status,
            confidence=s.verification_confidence,
            summary=s.verification_summary,
            verdict_at=s.verdict_at,
            decided_by_human=s.verdict_by is not None,
            requirements=[schemas.RequirementResultOut.model_validate(r) for r in rs],
            passed=sum(1 for r in rs if r.verdict == models.RequirementVerdict.passed),
            total=len(rs),
            failed_requirement=schemas.RequirementResultOut.model_validate(failed) if failed else None,
            steps=_steps(s, len(rs), s.id in with_views),
            appeal=(
                schemas.AppealOut(
                    id=appeal.id, status=appeal.status, reason=appeal.reason,
                    evidence_url=urls.get(appeal.evidence_upload_id) if appeal.evidence_upload_id else None,
                    decision_note=appeal.decision_note, created_at=appeal.created_at, decided_at=appeal.decided_at,
                )
                if appeal else None
            ),
        )
        out.append(
            schemas.SubmissionOut(
                id=s.id, campaign_id=s.campaign_id, creator_id=s.creator_id, platform=s.platform, url=s.url,
                title=s.title, video_url=urls.get(s.video_upload_id) if s.video_upload_id else None,
                status=s.status, rejection_code=s.rejection_code, rejection_message=s.rejection_message,
                created_at=s.created_at, updated_at=s.updated_at,
                campaign=(
                    schemas.SubmissionCampaignOut(
                        id=c.id, slug=c.slug, title=c.title,
                        brand_name=brand_map[c.event_manager_id].name if c.event_manager_id in brand_map else None,
                    ) if c else None
                ),
                verification=verification,
                resubmitted_from_id=s.resubmitted_from_id,
            )
        )
    return out
