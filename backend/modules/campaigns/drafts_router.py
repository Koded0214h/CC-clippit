"""The campaign studio's resumable draft lifecycle
(production-api-inventory.md §H) — `POST /campaigns` still exists for API
clients with a complete payload already in hand; the six-screen builder
should autosave through here instead."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from modules.auth.deps import get_verified_user
from modules.auth.models import Role, User
from modules.uploads.router import owned_upload

from . import models, schemas, service

router = APIRouter(prefix="/campaign-drafts", tags=["campaigns"])


def _require_organisation(user: User) -> None:
    if user.role != Role.organisation:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an organisation account can build a campaign")


async def _load_owned(draft_id: uuid.UUID, user: User, db: AsyncSession) -> models.CampaignDraft:
    draft = await db.get(models.CampaignDraft, draft_id)
    if draft is None or (draft.organisation_id != user.id and user.role != Role.admin):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found")
    return draft


def _out(draft: models.CampaignDraft) -> schemas.CampaignDraftOut:
    status_ = "finalized" if draft.finalized_campaign_id else ("in_progress" if draft.draft_answers else "not_started")
    return schemas.CampaignDraftOut(
        id=draft.id,
        schema_version=draft.schema_version,
        status=status_,
        step=draft.current_step,
        revision=draft.revision,
        answers=draft.draft_answers,
        blockers={} if draft.finalized_campaign_id else service.draft_blockers(draft.draft_answers),
        finalized_campaign_id=draft.finalized_campaign_id,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


@router.post("", response_model=schemas.CampaignDraftOut, status_code=status.HTTP_201_CREATED)
async def create_draft(user: User = Depends(get_verified_user), db: AsyncSession = Depends(get_db)):
    _require_organisation(user)
    draft = models.CampaignDraft(organisation_id=user.id)
    db.add(draft)
    await db.commit()
    await db.refresh(draft)
    return _out(draft)


@router.get("", response_model=list[schemas.CampaignDraftOut])
async def list_drafts(user: User = Depends(get_verified_user), db: AsyncSession = Depends(get_db)):
    """In-progress only — a finalized draft's real campaign has its own
    place in `GET /campaigns`; it doesn't also linger here."""
    _require_organisation(user)
    rows = await db.scalars(
        select(models.CampaignDraft)
        .where(models.CampaignDraft.organisation_id == user.id, models.CampaignDraft.finalized_campaign_id.is_(None))
        .order_by(models.CampaignDraft.updated_at.desc())
    )
    return [_out(d) for d in rows]


@router.get("/{draft_id}", response_model=schemas.CampaignDraftOut)
async def get_draft(draft_id: uuid.UUID, user: User = Depends(get_verified_user), db: AsyncSession = Depends(get_db)):
    return _out(await _load_owned(draft_id, user, db))


@router.patch("/{draft_id}", response_model=schemas.CampaignDraftOut)
async def patch_draft(
    draft_id: uuid.UUID,
    payload: schemas.CampaignDraftPatch,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    draft = await _load_owned(draft_id, user, db)
    if draft.finalized_campaign_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This draft was already finalized into a campaign.")
    if payload.revision != draft.revision:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This draft moved on since you last read it (at revision {draft.revision}). Reload and reapply your change.",
        )
    if payload.cover_image_upload_id is not None:
        await owned_upload(db, payload.cover_image_upload_id, user.id, kinds=("image",))

    changes = payload.model_dump(mode="json", exclude_unset=True, exclude={"revision", "step"})
    answers = dict(draft.draft_answers or {})
    # `exclude_unset` already separates an omitted answer from one the brand
    # explicitly cleared. Keep explicit nulls so optional values such as a
    # duration, conversion setup or source link can actually be removed.
    answers.update(changes)
    draft.draft_answers = answers
    if payload.step is not None:
        draft.current_step = payload.step
    draft.revision += 1
    await db.commit()
    await db.refresh(draft)
    return _out(draft)


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(draft_id: uuid.UUID, user: User = Depends(get_verified_user), db: AsyncSession = Depends(get_db)):
    draft = await _load_owned(draft_id, user, db)
    if draft.finalized_campaign_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This draft was already finalized — delete the campaign instead.")
    await db.delete(draft)
    await db.commit()


@router.post("/{draft_id}/finalize", response_model=schemas.CampaignDraftFinalizeOut)
async def finalize_draft(
    draft_id: uuid.UUID, user: User = Depends(get_verified_user), db: AsyncSession = Depends(get_db)
):
    _require_organisation(user)
    draft = await _load_owned(draft_id, user, db)
    try:
        campaign = await service.finalize_draft(db, draft, user)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await db.commit()
    return schemas.CampaignDraftFinalizeOut(
        campaign_id=campaign.id, campaign_slug=campaign.slug, next_route=f"/brand/campaigns/{campaign.slug}/fund"
    )
