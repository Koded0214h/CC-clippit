"""File storage behind one interface. Local disk, or Cloudinary (staged
through the same local-disk path, then uploaded and cleaned up — see
`CloudinaryStorage`).

Uploads are streamed to disk in chunks and abort the moment they pass the
size limit — a 250MB video is never held in memory, and an oversized one is
never fully written.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import cloudinary
import cloudinary.uploader

from .config import get_settings

CHUNK = 1024 * 1024


class UploadRejected(ValueError):
    """The file is not acceptable. The message is safe to show a user."""


@dataclass(frozen=True)
class StoredFile:
    key: str
    size_bytes: int
    content_type: str


#: kind -> (allowed extensions, signature check, byte limit setting)
def _looks_like_image(head: bytes) -> str | None:
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return None


def _looks_like_video(head: bytes) -> str | None:
    # ISO base media (mp4 / mov) starts with a size then the `ftyp` box.
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "video/quicktime" if head[8:12] == b"qt  " else "video/mp4"
    return None


_SNIFFERS = {"image": _looks_like_image, "video": _looks_like_video}
_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
}


class Storage(Protocol):
    async def save(self, chunks, *, kind: str, max_bytes: int) -> StoredFile: ...

    def url_for(self, key: str) -> str: ...

    def path_for(self, key: str) -> Path | None: ...

    # --- multipart (production-api-inventory.md §P) -------------------------
    # A real R2/S3 backend would hand back *signed* per-part PUT URLs the
    # client uploads straight to; this local backend has no such thing to
    # sign, so its "part URL" is just a path on this same API
    # (`PUT /uploads/multipart/{upload_id}/parts/{n}`) and completion reads
    # what landed on disk instead of asking the provider to assemble parts.
    # Swapping in a real R2Storage only needs these three methods to hand
    # back genuine presigned URLs and do a real CompleteMultipartUpload.

    def part_path(self, upload_id: uuid.UUID, part_number: int) -> Path: ...

    async def save_part(self, upload_id: uuid.UUID, part_number: int, chunks) -> int: ...

    async def assemble(self, upload_id: uuid.UUID, part_numbers: list[int], *, kind: str, max_bytes: int) -> StoredFile: ...


class LocalStorage:
    def __init__(self, root: str, public_base_url: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._base = public_base_url.rstrip("/")

    async def save(self, chunks, *, kind: str, max_bytes: int) -> StoredFile:
        """`chunks` is an async iterator of bytes. `kind` is `image`, `video`
        or `evidence` (image or video)."""
        sniff_kinds = ("image", "video") if kind == "evidence" else (kind,)
        size = 0
        head = b""
        content_type: str | None = None
        target: Path | None = None
        handle = None
        try:
            async for chunk in chunks:
                if not chunk:
                    continue
                if handle is None:
                    head = chunk[:32]
                    for candidate in sniff_kinds:
                        content_type = _SNIFFERS[candidate](head)
                        if content_type:
                            break
                    if not content_type:
                        raise UploadRejected(
                            "That file type isn't supported."
                            if kind == "evidence"
                            else f"That doesn't look like a valid {kind} file."
                        )
                    key = f"{kind}/{uuid.uuid4().hex}{_EXTENSIONS[content_type]}"
                    target = self.root / key
                    target.parent.mkdir(parents=True, exist_ok=True)
                    handle = target.open("wb")
                size += len(chunk)
                if size > max_bytes:
                    raise UploadRejected(f"That file is larger than {max_bytes // (1024 * 1024)}MB.")
                handle.write(chunk)
            if handle is None or not content_type or target is None:
                raise UploadRejected("The file is empty.")
        except BaseException:
            if handle is not None:
                handle.close()
                handle = None
            if target is not None and target.exists():
                target.unlink()
            raise
        finally:
            if handle is not None:
                handle.close()
        return StoredFile(key=str(target.relative_to(self.root)), size_bytes=size, content_type=content_type)

    def url_for(self, key: str) -> str:
        return f"{self._base}/media/{key}"

    def path_for(self, key: str) -> Path | None:
        path = (self.root / key).resolve()
        if self.root not in path.parents or not path.exists():
            return None
        return path

    # --- multipart ------------------------------------------------------------

    def _pending_dir(self, upload_id: uuid.UUID) -> Path:
        d = self.root / "pending" / str(upload_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def part_path(self, upload_id: uuid.UUID, part_number: int) -> Path:
        return self._pending_dir(upload_id) / f"part-{part_number:05d}"

    async def save_part(self, upload_id: uuid.UUID, part_number: int, chunks) -> int:
        target = self.part_path(upload_id, part_number)
        size = 0
        with target.open("wb") as handle:
            async for chunk in chunks:
                if not chunk:
                    continue
                size += len(chunk)
                handle.write(chunk)
        return size

    async def assemble(self, upload_id: uuid.UUID, part_numbers: list[int], *, kind: str, max_bytes: int) -> StoredFile:
        sniff_kinds = ("image", "video") if kind == "evidence" else (kind,)
        parts = [self.part_path(upload_id, n) for n in sorted(part_numbers)]
        missing = [p for p in parts if not p.exists()]
        if missing:
            raise UploadRejected(f"Part {missing[0].name} was never uploaded.")

        size = sum(p.stat().st_size for p in parts)
        if size > max_bytes:
            self._cleanup_pending(upload_id)
            raise UploadRejected(f"That file is larger than {max_bytes // (1024 * 1024)}MB.")

        head = b""
        with parts[0].open("rb") as f:
            head = f.read(32)
        content_type = None
        for candidate in sniff_kinds:
            content_type = _SNIFFERS[candidate](head)
            if content_type:
                break
        if not content_type:
            self._cleanup_pending(upload_id)
            raise UploadRejected(
                "That file type isn't supported." if kind == "evidence" else f"That doesn't look like a valid {kind} file."
            )

        key = f"{kind}/{uuid.uuid4().hex}{_EXTENSIONS[content_type]}"
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as out:
            for part in parts:
                out.write(part.read_bytes())
        self._cleanup_pending(upload_id)
        return StoredFile(key=key, size_bytes=size, content_type=content_type)

    def _cleanup_pending(self, upload_id: uuid.UUID) -> None:
        import shutil

        shutil.rmtree(self.root / "pending" / str(upload_id), ignore_errors=True)


class CloudinaryStorage:
    """Stages the same way `LocalStorage` does — streamed to disk, sniffed,
    size-checked, so a 250MB video is never held fully in memory — then
    uploads the staged file to Cloudinary and deletes the local copy.
    `key` is the Cloudinary `secure_url` itself, so `url_for` is an
    identity return and no second lookup is ever needed; `path_for` is
    always `None` since nothing is served from this process."""

    def __init__(self, cloud_name: str, api_key: str, api_secret: str, staging_dir: str) -> None:
        cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret, secure=True)
        self._staging = LocalStorage(staging_dir, public_base_url="")

    async def save(self, chunks, *, kind: str, max_bytes: int) -> StoredFile:
        staged = await self._staging.save(chunks, kind=kind, max_bytes=max_bytes)
        return await self._upload_and_cleanup(staged, kind)

    def url_for(self, key: str) -> str:
        return key

    def path_for(self, key: str) -> Path | None:
        return None

    def part_path(self, upload_id: uuid.UUID, part_number: int) -> Path:
        return self._staging.part_path(upload_id, part_number)

    async def save_part(self, upload_id: uuid.UUID, part_number: int, chunks) -> int:
        return await self._staging.save_part(upload_id, part_number, chunks)

    async def assemble(self, upload_id: uuid.UUID, part_numbers: list[int], *, kind: str, max_bytes: int) -> StoredFile:
        staged = await self._staging.assemble(upload_id, part_numbers, kind=kind, max_bytes=max_bytes)
        return await self._upload_and_cleanup(staged, kind)

    async def _upload_and_cleanup(self, staged: StoredFile, kind: str) -> StoredFile:
        local_path = self._staging.root / staged.key
        resource_type = "video" if staged.content_type.startswith("video/") else "image"
        try:
            result = await asyncio.to_thread(
                cloudinary.uploader.upload_large, str(local_path), resource_type=resource_type, folder=f"clippit/{kind}",
            )
        finally:
            local_path.unlink(missing_ok=True)
        return StoredFile(key=result["secure_url"], size_bytes=staged.size_bytes, content_type=staged.content_type)


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_local_dir, settings.public_base_url)
    if settings.storage_backend == "cloudinary":
        if not (settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret):
            raise RuntimeError("STORAGE_BACKEND=cloudinary needs CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET set")
        return CloudinaryStorage(
            settings.cloudinary_cloud_name, settings.cloudinary_api_key, settings.cloudinary_api_secret,
            settings.storage_local_dir,
        )
    raise RuntimeError(f"Unknown STORAGE_BACKEND {settings.storage_backend!r}")
