import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.deps import get_db
from core.rate_limit import limiter
from core.storage import CHUNK, Storage, UploadRejected, get_storage
from modules.auth.deps import get_current_user, get_verified_user
from modules.auth.models import User

from . import models, schemas

router = APIRouter(prefix="/uploads", tags=["uploads"])
media_router = APIRouter(tags=["uploads"])


async def _chunks(file: UploadFile) -> AsyncIterator[bytes]:
    while chunk := await file.read(CHUNK):
        yield chunk


async def _store(
    file: UploadFile, kind: str, max_bytes: int, user: User, db: AsyncSession, storage: Storage
) -> schemas.UploadOut:
    try:
        stored = await storage.save(_chunks(file), kind=kind, max_bytes=max_bytes)
    except UploadRejected as exc:
        # Literal codes: Starlette is mid-rename on the constant names.
        raise HTTPException(413 if "larger than" in str(exc) else 422, str(exc)) from exc

    upload = models.Upload(
        owner_id=user.id,
        kind=kind,
        key=stored.key,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
    )
    db.add(upload)
    await db.commit()
    await db.refresh(upload)
    return schemas.UploadOut(
        id=upload.id,
        kind=upload.kind,
        url=storage.url_for(upload.key),
        content_type=upload.content_type,
        size_bytes=upload.size_bytes,
        created_at=upload.created_at,
    )


@router.post("/images", response_model=schemas.UploadOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def upload_image(
    request: Request,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
):
    """Profile photos, organisation logos, campaign covers."""
    return await _store(file, "image", get_settings().max_image_bytes, user, db, storage)


@router.post("/videos", response_model=schemas.UploadOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def upload_video(
    request: Request,
    file: UploadFile,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
):
    """The original file behind a submission (MP4 or MOV)."""
    return await _store(file, "video", get_settings().max_video_bytes, user, db, storage)


@router.post("/evidence", response_model=schemas.UploadOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def upload_evidence(
    request: Request,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
):
    """A screenshot or screen recording supporting an appeal."""
    return await _store(file, "evidence", get_settings().max_evidence_bytes, user, db, storage)


async def owned_upload(
    db: AsyncSession, upload_id: uuid.UUID, owner_id: uuid.UUID, *, kinds: tuple[str, ...]
) -> models.Upload:
    """The upload, only if this user owns it, is the right kind, and has
    actually finished uploading. Other modules call this rather than
    trusting an id from a request body."""
    upload = await db.get(models.Upload, upload_id)
    if upload is None or upload.owner_id != owner_id or upload.kind not in kinds or upload.status != "ready":
        raise HTTPException(422, "That upload can't be used here.")
    return upload


@router.post("/support-attachments", response_model=schemas.UploadOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def upload_support_attachment(
    request: Request,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
):
    """A ticket/dispute attachment. Reuses the `evidence` pipeline (image or
    video, sniffed not trusted) rather than a distinct kind — the type and
    size rules are the same, only the caller differs."""
    return await _store(file, "evidence", get_settings().max_evidence_bytes, user, db, storage)


# --- multipart (production-api-inventory.md §P) -----------------------------
# See core.storage.Storage's docstring: this local backend simulates the
# contract with one part landing on our own disk, not several signed R2
# PUT URLs — the shape production swaps behind the same interface.

_MULTIPART_TTL_MINUTES = 60
_MAX_BY_KIND = {
    "image": lambda s: s.max_image_bytes,
    "video": lambda s: s.max_video_bytes,
    "evidence": lambda s: s.max_evidence_bytes,
}


@router.post("/multipart", response_model=schemas.MultipartCreated, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_multipart_upload(
    request: Request,
    payload: schemas.MultipartCreate,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    max_bytes = _MAX_BY_KIND[payload.kind](settings)
    if payload.declared_size_bytes > max_bytes:
        raise HTTPException(413, f"That file is larger than {max_bytes // (1024 * 1024)}MB.")

    upload = models.Upload(owner_id=user.id, kind=payload.kind, status="pending")
    db.add(upload)
    await db.commit()
    await db.refresh(upload)

    from datetime import datetime, timedelta, timezone

    return schemas.MultipartCreated(
        upload_id=upload.id,
        part_urls=[f"/uploads/multipart/{upload.id}/parts/1"],
        part_size_bytes=payload.declared_size_bytes,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=_MULTIPART_TTL_MINUTES),
    )


async def _pending_owned(db: AsyncSession, upload_id: uuid.UUID, owner_id: uuid.UUID) -> models.Upload:
    upload = await db.get(models.Upload, upload_id)
    if upload is None or upload.owner_id != owner_id or upload.status != "pending":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending upload here.")
    return upload


@router.put("/multipart/{upload_id}/parts/{part_number}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def upload_part(
    request: Request,
    upload_id: uuid.UUID,
    part_number: int,
    file: UploadFile,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
):
    await _pending_owned(db, upload_id, user.id)
    await storage.save_part(upload_id, part_number, _chunks(file))


@router.post("/multipart/{upload_id}/complete", response_model=schemas.UploadOut)
@limiter.limit("10/minute")
async def complete_multipart_upload(
    request: Request,
    upload_id: uuid.UUID,
    payload: schemas.MultipartComplete,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
):
    """Verifies what actually landed on disk — byte signature, size,
    ownership — before this upload can be referenced anywhere. No
    scan/transcode/thumbnail pipeline runs yet (still open)."""
    upload = await _pending_owned(db, upload_id, user.id)
    max_bytes = _MAX_BY_KIND[upload.kind](get_settings())
    try:
        stored = await storage.assemble(upload_id, payload.part_numbers, kind=upload.kind, max_bytes=max_bytes)
    except UploadRejected as exc:
        upload.status = "failed"
        await db.commit()
        raise HTTPException(413 if "larger than" in str(exc) else 422, str(exc)) from exc

    upload.key = stored.key
    upload.content_type = stored.content_type
    upload.size_bytes = stored.size_bytes
    upload.status = "ready"
    await db.commit()
    await db.refresh(upload)
    return schemas.UploadOut(
        id=upload.id, kind=upload.kind, url=storage.url_for(upload.key), content_type=upload.content_type,
        size_bytes=upload.size_bytes, created_at=upload.created_at,
    )


@router.get("/{upload_id}", response_model=schemas.UploadStatusOut)
async def get_upload(
    upload_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
):
    upload = await db.get(models.Upload, upload_id)
    if upload is None or upload.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload not found")
    return schemas.UploadStatusOut(
        id=upload.id, kind=upload.kind, status=upload.status,
        url=storage.url_for(upload.key) if upload.key else None,
        content_type=upload.content_type, size_bytes=upload.size_bytes, created_at=upload.created_at,
    )


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload(upload_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Deletes an unattached owned upload. Refuses one that's already
    referenced by a submission, profile, appeal, dispute, or report — those
    are evidence/finance-adjacent records, not scratch files."""
    upload = await db.get(models.Upload, upload_id)
    if upload is None or upload.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload not found")

    from modules.campaigns.models import Campaign
    from modules.creators.models import CreatorProfile
    from modules.organisations.models import OrganisationProfile
    from modules.submissions.models import Submission, SubmissionAppeal

    referenced = (
        await db.scalar(select(Submission.id).where(Submission.video_upload_id == upload_id))
        or await db.scalar(select(SubmissionAppeal.id).where(SubmissionAppeal.evidence_upload_id == upload_id))
        or await db.scalar(select(CreatorProfile.user_id).where(CreatorProfile.photo_upload_id == upload_id))
        or await db.scalar(select(OrganisationProfile.user_id).where(OrganisationProfile.photo_upload_id == upload_id))
        or await db.scalar(select(Campaign.id).where(Campaign.cover_image_upload_id == upload_id))
    )
    if referenced:
        raise HTTPException(status.HTTP_409_CONFLICT, "This file is in use and can't be deleted.")
    await db.delete(upload)
    await db.commit()


@media_router.get("/media/{key:path}", include_in_schema=False)
async def serve_media(key: str, storage: Storage = Depends(get_storage)):
    """Serves an uploaded file. Keys are unguessable UUIDs and `path_for`
    refuses anything that resolves outside the storage root. Replaced by
    signed R2 URLs in production."""
    path = storage.path_for(key)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return FileResponse(path)
