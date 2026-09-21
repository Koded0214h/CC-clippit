"""File storage behind one interface. Local disk today; Cloudflare R2 is the
plan's production target and replaces `LocalStorage` without touching a
caller.

Uploads are streamed to disk in chunks and abort the moment they pass the
size limit — a 250MB video is never held in memory, and an oversized one is
never fully written.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

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


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend != "local":
        raise RuntimeError(f"Unknown STORAGE_BACKEND {settings.storage_backend!r}")
    return LocalStorage(settings.storage_local_dir, settings.public_base_url)
