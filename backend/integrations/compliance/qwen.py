"""Qwen3.8-Omni-Flash client — native video + audio brief checking.

Talks to Alibaba Cloud Model Studio via the OpenAI-compatible Chat
Completions API. Omni requires `stream=True`; we drain the stream into a
single text judgement and parse structured JSON from it.
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .errors import ModelError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen3.8-omni-flash"
DEFAULT_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
#: Encoded Base64 payload must stay under ~10MB per Model Studio docs.
MAX_DATA_URL_BYTES = 7 * 1024 * 1024


@dataclass(frozen=True)
class RuleSpec:
    id: str
    kind: str
    text: str


@dataclass(frozen=True)
class RuleJudgement:
    rule_id: str
    result: str  # pass | fail | uncertain
    evidence: str | None = None
    timestamps: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class QwenJudgement:
    overall: str  # APPROVED | REJECTED | HUMAN_REVIEW_REQUIRED
    confidence: float | None
    rules: list[RuleJudgement]
    human_review_reason: str | None
    summary: str | None
    model: str
    raw_text: str


class QwenClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = 180.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ModelError("DASHSCOPE_API_KEY / QWEN_API_KEY is not configured.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._transport = transport

    @property
    def model(self) -> str:
        return self._model

    async def judge_video(
        self,
        *,
        rules: list[RuleSpec],
        video_url: str | None = None,
        video_path: Path | None = None,
        campaign_title: str | None = None,
    ) -> QwenJudgement:
        if not rules:
            raise ModelError("Refusing to call Qwen with an empty rule list.")
        content_url = video_url
        if content_url is None:
            if video_path is None:
                raise ModelError("judge_video requires video_url or video_path.")
            content_url = _data_url_for(video_path)

        prompt = _build_prompt(rules, campaign_title=campaign_title)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "video_url", "video_url": {"url": content_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        raw = await self._chat_text(messages)
        return parse_judgement(raw, rules=rules, model=self._model)

    async def _chat_text(self, messages: list[dict[str, Any]]) -> str:
        body = {
            "model": self._model,
            "messages": messages,
            "modalities": ["text"],
            "stream": True,
            "stream_options": {"include_usage": True},
            "enable_thinking": False,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/chat/completions"
        chunks: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                async with client.stream("POST", url, headers=headers, json=body) as resp:
                    if resp.status_code >= 400:
                        detail = (await resp.aread()).decode("utf-8", errors="replace")[:500]
                        raise ModelError(
                            f"Qwen API returned HTTP {resp.status_code}: {detail}",
                            code="model_http_error",
                        )
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        for choice in event.get("choices") or []:
                            delta = choice.get("delta") or {}
                            piece = delta.get("content")
                            if isinstance(piece, str):
                                chunks.append(piece)
                            elif isinstance(piece, list):
                                for part in piece:
                                    if isinstance(part, dict) and part.get("type") == "text":
                                        chunks.append(str(part.get("text") or ""))
        except ModelError:
            raise
        except httpx.HTTPError as exc:
            raise ModelError(f"Qwen request failed: {exc}") from exc

        text = "".join(chunks).strip()
        if not text:
            raise ModelError("Qwen returned an empty streaming response.")
        logger.info("qwen judgement chars=%s model=%s", len(text), self._model)
        return text


def _data_url_for(path: Path) -> str:
    size = path.stat().st_size
    if size > MAX_DATA_URL_BYTES:
        raise ModelError(
            f"Video at {path} is {size / (1024 * 1024):.1f}MB; Base64 local "
            f"upload limit is ~{MAX_DATA_URL_BYTES / (1024 * 1024):.0f}MB. "
            "Serve the file at a public HTTPS URL instead.",
            code="video_too_large_for_inline",
        )
    mime = mimetypes.guess_type(path.name)[0] or "video/mp4"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _build_prompt(rules: list[RuleSpec], *, campaign_title: str | None) -> str:
    lines = [
        "You are Clippit's campaign compliance checker.",
        "Watch and listen to the entire video (including audio).",
        "Evaluate EVERY campaign rule independently.",
        "Return ONLY valid JSON matching this schema (no markdown fences):",
        "{",
        '  "overall": "APPROVED" | "REJECTED" | "HUMAN_REVIEW_REQUIRED",',
        '  "confidence": number between 0 and 1,',
        '  "summary": "one short sentence",',
        '  "human_review_reason": string or null,',
        '  "rules": [',
        '    {"rule_id": "<id>", "result": "pass"|"fail"|"uncertain",',
        '     "evidence": "what in the video supports this",',
        '     "timestamps": ["mm:ss", ...]}',
        "  ]",
        "}",
        "",
        "Decision rules:",
        "- APPROVED only if every rule is pass.",
        "- REJECTED if any must-rule fails, or any avoid-rule is clearly violated.",
        "- HUMAN_REVIEW_REQUIRED if any rule is uncertain, or evidence is weak.",
        "- For kind=must: pass means the video clearly satisfies it.",
        "- For kind=avoid: pass means the video does NOT do/claim that thing.",
        "",
    ]
    if campaign_title:
        lines.append(f"Campaign: {campaign_title}")
        lines.append("")
    lines.append("Rules:")
    for rule in rules:
        lines.append(f"- id={rule.id} kind={rule.kind}: {rule.text}")
    return "\n".join(lines)


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_judgement(raw_text: str, *, rules: list[RuleSpec], model: str) -> QwenJudgement:
    """Parse model text into a judgement, tolerating markdown fences."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_RE.search(raw_text)
        if not match:
            raise ModelError("Qwen response was not valid JSON.") from None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ModelError("Qwen response was not valid JSON.") from exc

    if not isinstance(data, dict):
        raise ModelError("Qwen JSON root must be an object.")

    overall = str(data.get("overall") or "HUMAN_REVIEW_REQUIRED").upper()
    if overall not in {"APPROVED", "REJECTED", "HUMAN_REVIEW_REQUIRED"}:
        overall = "HUMAN_REVIEW_REQUIRED"

    confidence = data.get("confidence")
    try:
        confidence_f = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence_f = None
    if confidence_f is not None:
        confidence_f = max(0.0, min(1.0, confidence_f))

    by_id = {r.id: r for r in rules}
    judgements: list[RuleJudgement] = []
    seen: set[str] = set()
    for row in data.get("rules") or []:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("rule_id") or "")
        if rid not in by_id or rid in seen:
            continue
        seen.add(rid)
        result = str(row.get("result") or "uncertain").lower()
        if result not in {"pass", "fail", "uncertain"}:
            result = "uncertain"
        stamps = row.get("timestamps") or []
        if not isinstance(stamps, list):
            stamps = []
        judgements.append(
            RuleJudgement(
                rule_id=rid,
                result=result,
                evidence=(str(row["evidence"]) if row.get("evidence") is not None else None),
                timestamps=[str(s) for s in stamps],
            )
        )

    # Every rule must appear — fill gaps as uncertain so the product never
    # silently skips a campaign requirement.
    for rule in rules:
        if rule.id not in seen:
            judgements.append(
                RuleJudgement(
                    rule_id=rule.id,
                    result="uncertain",
                    evidence="Model did not return a verdict for this rule.",
                )
            )

    # If the model claimed APPROVED but any rule isn't pass, demote.
    if overall == "APPROVED" and any(j.result != "pass" for j in judgements):
        overall = "HUMAN_REVIEW_REQUIRED"
    if overall == "REJECTED" and all(j.result == "pass" for j in judgements):
        overall = "HUMAN_REVIEW_REQUIRED"

    return QwenJudgement(
        overall=overall,
        confidence=confidence_f,
        rules=judgements,
        human_review_reason=(
            str(data["human_review_reason"]) if data.get("human_review_reason") is not None else None
        ),
        summary=str(data["summary"]) if data.get("summary") is not None else None,
        model=model,
        raw_text=raw_text,
    )
