"""Qwen-backed Verifier — yt-dlp retrieve, Omni judge, structured Outcome.

Wired through `get_verifier()` when `COMPLIANCE_VERIFIER=qwen`. Technical
failures never become content rejections (PRD §7.3 / §14.2).
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from core.config import get_settings
from integrations.compliance import (
    MediaRetrievalError,
    ModelError,
    QwenClient,
    retrieve_video,
)
from integrations.compliance.qwen import RuleSpec
from modules.campaigns.models import Campaign, CampaignRule

from .models import RequirementVerdict, Submission, VerificationStatus
from .verification import Outcome, RequirementCheck

logger = logging.getLogger(__name__)


class QwenComplianceVerifier:
    """PRD V1 compliance engine: URL → yt-dlp → Qwen3.8-Omni-Flash."""

    async def verify(
        self, *, submission: Submission, campaign: Campaign, rules: list[CampaignRule]
    ) -> Outcome:
        if not rules:
            return Outcome(
                status=VerificationStatus.approved,
                summary="This campaign has no requirements to check.",
                model=None,
            )

        settings = get_settings()
        dest = Path(settings.compliance_media_dir) / str(submission.id)
        media_path: Path | None = None
        try:
            media = retrieve_video(
                submission.url,
                dest,
                max_duration_s=settings.compliance_max_duration_seconds,
                max_filesize_mb=settings.compliance_max_filesize_mb,
            )
            media_path = media.path
            client = QwenClient(
                api_key=settings.dashscope_api_key or settings.qwen_api_key,
                base_url=settings.qwen_base_url,
                model=settings.qwen_model,
            )
            video_url = _public_video_url(media.path, settings)
            judgement = await client.judge_video(
                rules=[RuleSpec(id=str(r.id), kind=r.kind.value, text=r.text) for r in rules],
                video_url=video_url,
                video_path=None if video_url else media.path,
                campaign_title=campaign.title,
            )
        except (MediaRetrievalError, ModelError) as exc:
            logger.warning(
                "compliance technical failure submission=%s code=%s err=%s",
                submission.id,
                getattr(exc, "code", "compliance_error"),
                exc,
            )
            return _technical_failure(rules, exc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("unexpected compliance failure submission=%s", submission.id)
            return _technical_failure(rules, ModelError(f"Unexpected compliance error: {exc}"))

        by_id = {str(r.id): r for r in rules}
        checks: list[RequirementCheck] = []
        for item in judgement.rules:
            rule = by_id.get(item.rule_id)
            if rule is None:
                continue
            note_parts = [p for p in (item.evidence, _fmt_timestamps(item.timestamps)) if p]
            checks.append(
                RequirementCheck(
                    rule=rule,
                    verdict=_map_result(item.result),
                    note=" · ".join(note_parts) if note_parts else None,
                )
            )
        # Preserve campaign rule order.
        order = {str(r.id): i for i, r in enumerate(rules)}
        checks.sort(key=lambda c: order.get(str(c.rule.id), 0))

        status = _map_overall(judgement.overall)
        summary = judgement.summary or judgement.human_review_reason
        if status == VerificationStatus.needs_review and judgement.human_review_reason:
            summary = judgement.human_review_reason
        if summary:
            summary = f"[{judgement.model}] {summary}"

        # Keep media on disk for audit when configured; otherwise tidy up.
        if not settings.compliance_keep_media and media_path is not None:
            shutil.rmtree(dest, ignore_errors=True)

        conf = judgement.confidence
        return Outcome(
            status=status,
            checks=checks,
            confidence=(conf * 100.0) if conf is not None else None,
            summary=summary,
            model=judgement.model,
            media_path=str(media_path) if media_path and settings.compliance_keep_media else None,
        )


def _map_result(result: str) -> RequirementVerdict:
    if result == "pass":
        return RequirementVerdict.passed
    if result == "fail":
        return RequirementVerdict.failed
    return RequirementVerdict.review


def _map_overall(overall: str) -> VerificationStatus:
    if overall == "APPROVED":
        return VerificationStatus.approved
    if overall == "REJECTED":
        return VerificationStatus.rejected
    return VerificationStatus.needs_review


def _technical_failure(rules: list[CampaignRule], exc: Exception) -> Outcome:
    message = str(exc) or "Compliance check could not complete."
    code = getattr(exc, "code", "compliance_error")
    return Outcome(
        status=VerificationStatus.needs_review,
        summary=f"Technical failure ({code}): {message}",
        checks=[
            RequirementCheck(
                rule=r,
                verdict=RequirementVerdict.review,
                note="Skipped — compliance engine hit a technical failure.",
            )
            for r in rules
        ],
        confidence=None,
        model=None,
    )


def _fmt_timestamps(stamps: list[str]) -> str | None:
    if not stamps:
        return None
    return "at " + ", ".join(stamps)


def _public_video_url(path: Path, settings) -> str | None:
    """If COMPLIANCE_PUBLIC_MEDIA_BASE is set, copy/link under a public path.

    Model Studio cannot fetch localhost. When no public base is configured
    we fall back to an inline Base64 data URL (size-limited).
    """
    base = (settings.compliance_public_media_base or "").rstrip("/")
    if not base:
        return None
    # Expect files already under compliance_media_dir; expose as
    # {base}/{submission_id}/{filename}.
    media_root = Path(settings.compliance_media_dir).resolve()
    try:
        rel = path.resolve().relative_to(media_root)
    except ValueError:
        return None
    return f"{base}/{rel.as_posix()}"
