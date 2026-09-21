import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
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
    """The upload, only if this user owns it and it's the right kind. Other
    modules call this rather than trusting an id from a request body."""
    upload = await db.get(models.Upload, upload_id)
    if upload is None or upload.owner_id != owner_id or upload.kind not in kinds:
        raise HTTPException(422, "That upload can't be used here.")
    return upload


@media_router.get("/media/{key:path}", include_in_schema=False)
async def serve_media(key: str, storage: Storage = Depends(get_storage)):
    """Serves an uploaded file. Keys are unguessable UUIDs and `path_for`
    refuses anything that resolves outside the storage root. Replaced by
    signed R2 URLs in production."""
    path = storage.path_for(key)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return FileResponse(path)
