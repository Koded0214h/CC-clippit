"""Download the creator's posted video with yt-dlp.

Creators submit a live social URL only (PRD). We retrieve the media for
Qwen to watch — the creator never re-uploads the file for compliance.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import MediaRetrievalError

logger = logging.getLogger(__name__)

#: Omni-Flash accepts ~150s of video; keep a soft ceiling here.
DEFAULT_MAX_DURATION_S = 150
DEFAULT_MAX_FILESIZE_MB = 80


@dataclass(frozen=True)
class RetrievedMedia:
    path: Path
    source_url: str
    title: str | None = None
    duration_s: float | None = None
    ext: str = "mp4"


def retrieve_video(
    url: str,
    dest_dir: Path,
    *,
    max_duration_s: int = DEFAULT_MAX_DURATION_S,
    max_filesize_mb: int = DEFAULT_MAX_FILESIZE_MB,
) -> RetrievedMedia:
    """Download the best short MP4 for `url` into `dest_dir`.

    Runs yt-dlp in-process. Raises `MediaRetrievalError` on any failure —
    never invents a path.
    """
    try:
        import yt_dlp
    except ImportError as exc:
        raise MediaRetrievalError(
            "yt-dlp is not installed. Add yt-dlp to the environment."
        ) from exc

    dest_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(dest_dir / "%(id)s.%(ext)s")
    max_bytes = max_filesize_mb * 1024 * 1024

    opts: dict = {
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "merge_output_format": "mp4",
        # Prefer a smaller download that still has audio for Omni.
        "format_sort": ["res:720", "tbr"],
        "noplaylist": True,
        "retries": 2,
        "fragment_retries": 2,
        "socket_timeout": 30,
    }
    if max_filesize_mb:
        opts["max_filesize"] = max_bytes

    info: dict | None = None
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise MediaRetrievalError(f"yt-dlp returned no info for {url!r}.")
            # Playlists / multi-entry shouldn't happen with noplaylist, but
            # guard anyway.
            if "entries" in info:
                entries = [e for e in (info.get("entries") or []) if e]
                if not entries:
                    raise MediaRetrievalError(f"yt-dlp found no downloadable entry for {url!r}.")
                info = entries[0]
            path = Path(ydl.prepare_filename(info))
            if path.suffix.lower() != ".mp4":
                # merge_output_format usually rewrites; fall back to sibling mp4.
                mp4 = path.with_suffix(".mp4")
                path = mp4 if mp4.exists() else path
    except MediaRetrievalError:
        raise
    except Exception as exc:  # noqa: BLE001 — yt-dlp raises many types
        raise MediaRetrievalError(f"Could not retrieve media from {url!r}: {exc}") from exc

    if not path.exists():
        # Sometimes the final name differs — scan the dest dir for newest file.
        candidates = sorted(dest_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        path = candidates[0] if candidates else path
    if not path.exists():
        raise MediaRetrievalError(f"yt-dlp finished but no file was written for {url!r}.")

    duration = info.get("duration")
    if duration is not None:
        try:
            duration_f = float(duration)
        except (TypeError, ValueError):
            duration_f = None
        else:
            if duration_f > max_duration_s:
                path.unlink(missing_ok=True)
                raise MediaRetrievalError(
                    f"Video is {duration_f:.0f}s; compliance limit is {max_duration_s}s "
                    "(Qwen3.8-Omni-Flash)."
                )
    else:
        duration_f = None

    size = path.stat().st_size
    if size > max_bytes:
        path.unlink(missing_ok=True)
        raise MediaRetrievalError(
            f"Downloaded file is {size / (1024 * 1024):.1f}MB; limit is {max_filesize_mb}MB."
        )
    if size < 1024:
        path.unlink(missing_ok=True)
        raise MediaRetrievalError("Downloaded file is empty or too small to be a real video.")

    title = info.get("title")
    if isinstance(title, str):
        title = re.sub(r"\s+", " ", title).strip() or None
    else:
        title = None

    logger.info("retrieved compliance media path=%s bytes=%s url=%s", path, size, url)
    return RetrievedMedia(
        path=path,
        source_url=url,
        title=title,
        duration_s=duration_f,
        ext=path.suffix.lstrip(".") or "mp4",
    )
