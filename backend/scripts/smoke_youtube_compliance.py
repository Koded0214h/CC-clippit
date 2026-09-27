"""Local smoke tests for YouTube Intelligence + Qwen compliance.

Does **not** keep videos. For compliance it: download → send to Qwen →
delete the scratch file.

Examples (from backend/):

    # 1) YouTube Data API only (needs YOUTUBE_API_KEY)
    python scripts/smoke_youtube_compliance.py youtube \\
        --url "https://www.youtube.com/watch?v=VIDEO_ID"

    # 2) yt-dlp download only (no Qwen) — proves retrieval + cleanup
    python scripts/smoke_youtube_compliance.py retrieve \\
        --url "https://www.youtube.com/watch?v=VIDEO_ID"

    # 3) Full compliance path (needs DASHSCOPE_API_KEY)
    python scripts/smoke_youtube_compliance.py compliance \\
        --url "https://www.youtube.com/watch?v=VIDEO_ID" \\
        --must "Must say the app is free" \\
        --avoid "Must not claim guaranteed returns"

    # 4) Both
    python scripts/smoke_youtube_compliance.py all \\
        --url "https://www.youtube.com/watch?v=VIDEO_ID" \\
        --must "Must show the product on screen"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

# Allow `python scripts/...` from backend/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _banner(title: str) -> None:
    print(f"\n{'═' * 64}\n{title}\n{'═' * 64}")


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}")


async def smoke_youtube(url: str) -> int:
    from core.config import get_settings
    from integrations.social.base import AdapterError
    from integrations.social.youtube import YouTubeAdapter

    _banner("YouTube Data API (Intelligence)")
    settings = get_settings()
    if not settings.youtube_api_key or len(settings.youtube_api_key.strip()) < 20:
        _fail(
            "YOUTUBE_API_KEY looks missing/placeholder. "
            "Create a Google Cloud API key with YouTube Data API v3 enabled."
        )
        return 1

    adapter = YouTubeAdapter()
    try:
        video_id = await adapter.resolve_url(url)
        if not video_id:
            _fail(f"URL not recognised as YouTube: {url}")
            return 1
        _ok(f"resolved video id = {video_id}")

        content = await adapter.get_content(video_id)
        _ok(f"channel = {content.author_username} ({content.author_platform_user_id})")
        _ok(f"title/caption = {(content.caption or '')[:80]!r}")

        metrics = await adapter.get_metrics(video_id)
        _ok(
            f"views={metrics.views} likes={metrics.likes} comments={metrics.comments} "
            f"source={adapter.source}"
        )
    except AdapterError as exc:
        _fail(str(exc))
        return 1

    print(
        json.dumps(
            {
                "platform_content_id": content.platform_content_id,
                "author_platform_user_id": content.author_platform_user_id,
                "views": metrics.views,
                "likes": metrics.likes,
                "comments": metrics.comments,
            },
            indent=2,
        )
    )
    return 0


async def smoke_retrieve(url: str) -> int:
    from integrations.compliance import retrieve_video

    _banner("yt-dlp retrieve (scratch only — will delete)")
    scratch = Path(tempfile.mkdtemp(prefix="clippit-retrieve-"))
    try:
        media = retrieve_video(url, scratch)
        size_mb = media.path.stat().st_size / (1024 * 1024)
        _ok(f"downloaded {media.path.name} ({size_mb:.2f} MB)")
        _ok(f"title={media.title!r} duration_s={media.duration_s}")
    except Exception as exc:  # noqa: BLE001
        _fail(str(exc))
        return 1
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        _ok(f"scratch deleted ({scratch})")
    return 0


async def smoke_compliance(url: str, must: list[str], avoid: list[str]) -> int:
    from core.config import get_settings
    from integrations.compliance import QwenClient, retrieve_video
    from integrations.compliance.qwen import RuleSpec

    _banner("Qwen compliance (download → judge → delete)")
    settings = get_settings()
    key = settings.dashscope_api_key or settings.qwen_api_key
    if not key:
        _fail("DASHSCOPE_API_KEY (or QWEN_API_KEY) is empty — cannot call Qwen")
        _fail("Add the key to backend/.env, then re-run.")
        return 1

    rules: list[RuleSpec] = []
    for text in must:
        rules.append(RuleSpec(id=str(uuid.uuid4()), kind="must", text=text))
    for text in avoid:
        rules.append(RuleSpec(id=str(uuid.uuid4()), kind="avoid", text=text))
    if not rules:
        rules = [
            RuleSpec(id=str(uuid.uuid4()), kind="must", text="Content is suitable for a brand campaign."),
        ]
        _ok("no rules passed — using one default must-rule")

    scratch = Path(tempfile.mkdtemp(prefix="clippit-compliance-"))
    try:
        media = retrieve_video(
            url,
            scratch,
            max_duration_s=settings.compliance_max_duration_seconds,
            max_filesize_mb=settings.compliance_max_filesize_mb,
        )
        size_mb = media.path.stat().st_size / (1024 * 1024)
        _ok(f"scratch download {media.path.name} ({size_mb:.2f} MB)")

        client = QwenClient(
            api_key=key,
            base_url=settings.qwen_base_url,
            model=settings.qwen_model,
        )
        _ok(f"calling {client.model} via {settings.qwen_base_url} …")
        judgement = await client.judge_video(
            rules=rules,
            video_path=media.path,
            campaign_title="Local smoke test",
        )
        print(
            json.dumps(
                {
                    "overall": judgement.overall,
                    "confidence": judgement.confidence,
                    "summary": judgement.summary,
                    "human_review_reason": judgement.human_review_reason,
                    "model": judgement.model,
                    "rules": [
                        {
                            "rule_id": r.rule_id,
                            "result": r.result,
                            "evidence": r.evidence,
                            "timestamps": r.timestamps,
                        }
                        for r in judgement.rules
                    ],
                },
                indent=2,
            )
        )
        _ok(f"overall = {judgement.overall}")
    except Exception as exc:  # noqa: BLE001
        _fail(str(exc))
        return 1
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        _ok(f"scratch deleted ({scratch}) — nothing stored")
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "mode",
        choices=("youtube", "retrieve", "compliance", "all"),
        help="which smoke path to run",
    )
    parser.add_argument("--url", required=True, help="public social / YouTube URL")
    parser.add_argument("--must", action="append", default=[], help="must-rule text (repeatable)")
    parser.add_argument("--avoid", action="append", default=[], help="avoid-rule text (repeatable)")
    parser.add_argument(
        "--cookies-from-browser",
        default=None,
        help="chrome|safari|firefox|edge — for YouTube bot-check on yt-dlp",
    )
    args = parser.parse_args()

    if args.cookies_from_browser:
        import os

        os.environ["YTDLP_COOKIES_FROM_BROWSER"] = args.cookies_from_browser
        from core.config import get_settings

        get_settings.cache_clear()

    rc = 0
    if args.mode in ("youtube", "all"):
        rc |= await smoke_youtube(args.url)
    if args.mode in ("retrieve", "all"):
        rc |= await smoke_retrieve(args.url)
    if args.mode in ("compliance", "all"):
        rc |= await smoke_compliance(args.url, args.must, args.avoid)
    return rc


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
