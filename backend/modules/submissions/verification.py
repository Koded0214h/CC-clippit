"""Brief verification — the seam D11 (unowned) will plug into.

A `Verifier` looks at a submission against the campaign's requirements and
returns a verdict per requirement plus an overall status. What runs behind
it is deliberately open: today the default hands everything to a person, and
the plan's automated checks (R2 + FFmpeg + Deepgram + an LLM reading the
brief) become another `Verifier` — nothing else in the app changes.

Whatever the verifier, one rule holds: **nothing earns until the submission
is `approved`**, and only a `Verifier` or a human decision can make it so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from modules.campaigns.models import Campaign, CampaignRule

from .models import RequirementVerdict, Submission, VerificationStatus


@dataclass
class RequirementCheck:
    rule: CampaignRule
    verdict: RequirementVerdict
    note: str | None = None


@dataclass
class Outcome:
    status: VerificationStatus
    checks: list[RequirementCheck] = field(default_factory=list)
    confidence: float | None = None
    summary: str | None = None


class Verifier(Protocol):
    async def verify(self, *, submission: Submission, campaign: Campaign, rules: list[CampaignRule]) -> Outcome: ...


class ManualReviewVerifier:
    """Every requirement goes to a human. A campaign with no requirements has
    nothing to check beyond post ownership (already proven when Intelligence
    accepted the link), so it's approved outright."""

    async def verify(self, *, submission: Submission, campaign: Campaign, rules: list[CampaignRule]) -> Outcome:
        if not rules:
            return Outcome(
                status=VerificationStatus.approved,
                summary="This campaign has no requirements to check.",
            )
        return Outcome(
            status=VerificationStatus.needs_review,
            summary="Waiting for the brand to check this clip against the brief.",
            checks=[
                RequirementCheck(rule=r, verdict=RequirementVerdict.review, note="Needs a person to check.")
                for r in rules
            ],
        )


def get_verifier() -> Verifier:
    return ManualReviewVerifier()
