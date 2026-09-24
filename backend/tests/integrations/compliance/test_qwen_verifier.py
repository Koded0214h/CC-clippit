"""Unit tests for Qwen judgement parsing and the compliance Verifier."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from integrations.compliance.qwen import RuleSpec, parse_judgement
from modules.campaigns.models import RuleKind
from modules.submissions import qwen_verifier
from modules.submissions.models import RequirementVerdict, VerificationStatus
from modules.submissions.qwen_verifier import QwenComplianceVerifier
from modules.submissions.verification import get_verifier, ManualReviewVerifier


def test_parse_judgement_fills_missing_rules_as_uncertain():
    rules = [
        RuleSpec(id="a", kind="must", text="Say free"),
        RuleSpec(id="b", kind="avoid", text="No guaranteed returns"),
    ]
    raw = json.dumps(
        {
            "overall": "APPROVED",
            "confidence": 0.9,
            "summary": "Looks good",
            "human_review_reason": None,
            "rules": [{"rule_id": "a", "result": "pass", "evidence": "Said free", "timestamps": ["0:03"]}],
        }
    )
    judgement = parse_judgement(raw, rules=rules, model="qwen3.8-omni-flash")
    assert judgement.overall == "HUMAN_REVIEW_REQUIRED"  # demoted — rule b missing/uncertain
    by_id = {r.rule_id: r for r in judgement.rules}
    assert by_id["a"].result == "pass"
    assert by_id["b"].result == "uncertain"


def test_parse_judgement_accepts_markdown_fence():
    rules = [RuleSpec(id="a", kind="must", text="Show product")]
    raw = """```json
{"overall":"REJECTED","confidence":0.8,"summary":"Missing product","human_review_reason":null,
 "rules":[{"rule_id":"a","result":"fail","evidence":"Never shown","timestamps":[]}]}
```"""
    judgement = parse_judgement(raw, rules=rules, model="qwen3.8-omni-flash")
    assert judgement.overall == "REJECTED"
    assert judgement.rules[0].result == "fail"


def test_get_verifier_defaults_to_manual(monkeypatch):
    from core.config import Settings, get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("COMPLIANCE_VERIFIER", "manual")
    get_settings.cache_clear()
    assert isinstance(get_verifier(), ManualReviewVerifier)
    get_settings.cache_clear()


async def test_qwen_verifier_technical_failure_does_not_reject(monkeypatch, tmp_path):
    from core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("COMPLIANCE_VERIFIER", "qwen")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv("COMPLIANCE_MEDIA_DIR", str(tmp_path))
    get_settings.cache_clear()

    def boom(*_a, **_k):
        from integrations.compliance import MediaRetrievalError

        raise MediaRetrievalError("yt-dlp failed")

    monkeypatch.setattr(qwen_verifier, "retrieve_video", boom)

    rule = SimpleNamespace(
        id=uuid.uuid4(),
        kind=RuleKind.must,
        text="Must say the app is free.",
    )
    submission = SimpleNamespace(id=uuid.uuid4(), url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    campaign = SimpleNamespace(title="Demo")

    outcome = await QwenComplianceVerifier().verify(
        submission=submission, campaign=campaign, rules=[rule]
    )
    assert outcome.status == VerificationStatus.needs_review
    assert outcome.summary and outcome.summary.startswith("Technical failure")
    assert outcome.checks[0].verdict == RequirementVerdict.review
    get_settings.cache_clear()


async def test_qwen_client_drains_sse_stream():
    from integrations.compliance.qwen import QwenClient, RuleSpec

    payload = {
        "overall": "APPROVED",
        "confidence": 0.95,
        "summary": "All good",
        "human_review_reason": None,
        "rules": [
            {
                "rule_id": "r1",
                "result": "pass",
                "evidence": "Said free at 0:02",
                "timestamps": ["0:02"],
            }
        ],
    }
    sse = (
        f"data: {json.dumps({'choices':[{'delta':{'content': json.dumps(payload)}}]})}\n\n"
        "data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})

    client = QwenClient(
        api_key="k",
        transport=httpx.MockTransport(handler),
    )
    judgement = await client.judge_video(
        rules=[RuleSpec(id="r1", kind="must", text="Say free")],
        video_url="https://example.com/clip.mp4",
    )
    assert judgement.overall == "APPROVED"
    assert judgement.rules[0].result == "pass"
