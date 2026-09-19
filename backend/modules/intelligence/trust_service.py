"""Running the trust rules against stored data, and writing down what
they said.

Kept apart from `trust.py` for the same reason `polling.py` is kept apart
from `scheduling.py`: the rules are the part that will change weekly and
needs to stay readable and replayable, while this is plumbing that should
change almost never.

The method that matters most here long-term is `replay()`. Because
snapshots are immutable and features are recomputable, a brand-new rule
set can be run across all history to see exactly what it *would* have
flagged. With no labels, that backtest is the only offline evaluation
available — and it's why new signals should run in shadow mode for a few
weeks before they're allowed to affect anyone's income.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from . import repository, trust
from .contracts import TrustResult, TrustSignal
from .models import MetricSnapshot, SocialContent, TrustEvaluation
from .timeutils import as_utc, utcnow
from .trust import Thresholds, TrustInput


class TrustService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        clock=utcnow,
        thresholds: Thresholds = trust.DEFAULT_THRESHOLDS,
    ) -> None:
        self._db = db
        self._clock = clock
        self._thresholds = thresholds

    async def evaluate_latest(self, content_id: uuid.UUID) -> TrustEvaluation | None:
        """Judge a post against its most recent observation.

        Called after every successful poll, in the same transaction that
        recorded the snapshot — so a stored observation is never visible
        without a verdict attached to it.
        """
        snapshot = await repository.latest_snapshot(self._db, content_id)
        if snapshot is None:
            return None
        return await self._evaluate_at(content_id, snapshot)

    async def replay(self, content_id: uuid.UUID) -> list[TrustEvaluation]:
        """Re-judge a post's entire history under the current rules.

        The backtest. Each observation is evaluated using only the data
        that existed up to that moment, so the output is what these rules
        would genuinely have said at the time — not a verdict with
        hindsight baked in.
        """
        snapshots = await repository.snapshots_for_content(self._db, content_id)
        return [await self._evaluate_at(content_id, snapshot) for snapshot in snapshots]

    async def result_for_submission(self, submission_id: uuid.UUID) -> TrustResult | None:
        """The current verdict, shaped for the world outside this module."""
        content = await repository.content_for_submission(self._db, submission_id)
        if content is None:
            return None

        evaluation = await repository.latest_evaluation(self._db, content.id)
        if evaluation is None:
            return None

        return TrustResult(
            submission_id=submission_id,
            status=evaluation.status,
            anomaly_score=evaluation.anomaly_score,
            # Re-validated on the way out rather than trusted blindly: these
            # were serialized under whatever the model looked like when they
            # were written, possibly months ago.
            signals=[TrustSignal.model_validate(s) for s in evaluation.signals],
            evaluated_at=as_utc(evaluation.evaluated_at),
        )

    # --- internals ---------------------------------------------------
    async def _evaluate_at(
        self, content_id: uuid.UUID, snapshot: MetricSnapshot
    ) -> TrustEvaluation:
        inp = await self._gather(content_id, snapshot)
        verdict = trust.evaluate(inp, self._thresholds)

        existing = await repository.evaluation_for_snapshot(self._db, snapshot.id)
        if existing is not None:
            # Re-evaluating the same observation replaces the opinion. Safe
            # here in a way it never is for a snapshot: this is a
            # conclusion, not a record of something that happened.
            existing.status = verdict.status
            existing.anomaly_score = verdict.anomaly_score
            existing.signals = trust.signals_to_json(verdict.signals)
            existing.evaluated_at = self._clock()
            await self._db.flush()
            return existing

        return await repository.add_evaluation(
            self._db,
            TrustEvaluation(
                content_id=content_id,
                snapshot_id=snapshot.id,
                evaluated_at=self._clock(),
                status=verdict.status,
                anomaly_score=verdict.anomaly_score,
                signals=trust.signals_to_json(verdict.signals),
            ),
        )

    async def _gather(self, content_id: uuid.UUID, snapshot: MetricSnapshot) -> TrustInput:
        """Collect exactly what the rules may see — and nothing after
        `snapshot`, so a replay can't cheat by looking into the future."""
        content = await self._db.get(SocialContent, content_id)
        cutoff = snapshot.captured_at

        snapshots = [
            s
            for s in await repository.snapshots_for_content(self._db, content_id)
            if as_utc(s.captured_at) <= as_utc(cutoff)
        ]
        features = await repository.features_for_content(self._db, content_id, until=cutoff)

        return TrustInput(
            platform=content.platform,
            snapshots=snapshots,
            features=features,
            duplicate_submissions=await repository.count_duplicate_content(
                self._db, content.platform, content.platform_content_id, exclude_id=content_id
            ),
        )


async def queue(
    db: AsyncSession, *, statuses: tuple[str, ...] = ("flagged", "watch"), limit: int = 50
) -> list[TrustEvaluation]:
    """The admin review queue: worst score first.

    Ranking by score is the *only* job the composite number has. The
    status decides what happens; the score decides who gets looked at
    first when there are more cases than reviewer hours.
    """
    return list(
        await db.scalars(
            sa.select(TrustEvaluation)
            .where(TrustEvaluation.status.in_(statuses))
            .order_by(TrustEvaluation.anomaly_score.desc(), TrustEvaluation.evaluated_at.desc())
            .limit(limit)
        )
    )
