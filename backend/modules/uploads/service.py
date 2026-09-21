import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.storage import get_storage

from . import models


async def url_for_upload(db: AsyncSession, upload_id: uuid.UUID | None) -> str | None:
    """The public URL for an upload id, or None. Kept out of the profile
    tables so a change of storage host never leaves stale URLs in them."""
    if upload_id is None:
        return None
    upload = await db.get(models.Upload, upload_id)
    return get_storage().url_for(upload.key) if upload else None
