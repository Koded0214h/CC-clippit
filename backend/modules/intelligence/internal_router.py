"""The only way into this module from the rest of Clippit.

Two routes, guarded by the same `X-Internal-Secret` the auth module uses.
Everything they return is a model from `contracts.py` — no ORM objects, no
provider payloads, no platform vocabulary. If Koded's earnings code can
bill from these responses without knowing what TikTok's Display API is,
the boundary is doing its job.

    POST /internal/submissions/{id}/metrics       observe now
    GET  /internal/submissions/{id}/performance   read what we know

The split between them matters: the POST talks to a platform and can
therefore be slow or fail, while the GET only reads our own tables and
never can. A billing run uses the GET, so nobody's payout waits on
TikTok's uptime.
"""

from __future__ import annotations

import uuid
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db, require_internal_secret
from integrations.social.base import (
    AdapterError,
    CapabilityNotSupported,
    ContentNotFound,
    ContentUnavailable,
    CreatorTokenExpired,
    RateLimited,
    UpstreamError,
)

from . import performance, repository, trust
from .contracts import PerformanceResult, SubmissionRef, TrustResult, TrustReviewIn
from .errors import MissingCreatorToken, TokenLookupFailed, UrlNotRecognized
from .models import TrustReview
from .polling import PollingCoordinator
from .trust_service import TrustService
from .worker import build_coordinator

router = APIRouter(
    prefix="/internal",
    tags=["intelligence-internal"],
    dependencies=[Depends(require_internal_secret)],
)


@lru_cache
def _coordinator() -> PollingCoordinator:
    """One coordinator for the process. Cached because it holds no
    per-request state — it opens its own session per unit of work — and
    because tests replace it wholesale via `dependency_overrides`."""
    return build_coordinator()


def get_coordinator() -> PollingCoordinator:
    return _coordinator()


#: How a failure to read a platform becomes an HTTP status. Ordered,
#: because `isinstance` is used and the specific classes have to be
#: checked before `AdapterError` catches everything.
#:
#: The distinction being encoded is "whose problem is this": 4xx means the
#: submission or the creator needs attention, 5xx means a machine does.
#: 422 is written as a literal because Starlette is mid-rename on that
#: constant (`..._UNPROCESSABLE_ENTITY` -> `..._UNPROCESSABLE_CONTENT`) and
#: the number is the stable part.
_HTTP_FAILURES: tuple[tuple[type[Exception], int, str], ...] = (
    (UrlNotRecognized, 422, "url_not_recognised"),
    (ContentNotFound, status.HTTP_404_NOT_FOUND, "content_not_found"),
    (ContentUnavailable, status.HTTP_409_CONFLICT, "content_unavailable"),
    (CreatorTokenExpired, status.HTTP_409_CONFLICT, "creator_reconnect_required"),
    (MissingCreatorToken, status.HTTP_409_CONFLICT, "creator_reconnect_required"),
    (CapabilityNotSupported, 422, "capability_not_supported"),
    (RateLimited, status.HTTP_503_SERVICE_UNAVAILABLE, "rate_limited"),
    (UpstreamError, status.HTTP_502_BAD_GATEWAY, "upstream_error"),
    (TokenLookupFailed, status.HTTP_502_BAD_GATEWAY, "upstream_error"),
    (AdapterError, status.HTTP_502_BAD_GATEWAY, "upstream_error"),
)


@router.post("/submissions/{submission_id}/metrics", response_model=PerformanceResult)
async def observe_now(
    submission_id: uuid.UUID,
    response: Response,
    payload: SubmissionRef | None = None,
    db: AsyncSession = Depends(get_db),
    coordinator: PollingCoordinator = Depends(get_coordinator),
):
    """Take a reading right now, and start tracking if this is new.

    Core calls this when a creator submits a link (with a `SubmissionRef`
    body, which registers the submission and puts it on the polling
    queue) and whenever someone wants a fresh number without waiting for
    the next scheduled poll (no body needed once we know the submission).

    Registration failures are raised as HTTP errors because there's a
    human waiting on the response — "that link isn't readable" is an
    answer they need now. A *re-observation* failure is different: the
    submission is already tracked, so the failure is recorded as a
    polling decision and shows up in `tracking` on a 200. Nothing is
    hidden either way; the difference is whether anyone is waiting.
    """
    # Only the ID, deliberately: the rollback below expires anything loaded
    # in this session, and a plain UUID survives that where an ORM object
    # would try to reload itself mid-request.
    content_id = await repository.content_id_for_submission(db, submission_id)
    # Let go of this session's read transaction before handing off. The
    # coordinator opens and commits its own (so the re-read at the end sees
    # its writes), and holding a transaction open across a call to a
    # platform API is how a connection pool dies under load.
    await db.rollback()

    try:
        if content_id is not None:
            await coordinator.poll(content_id)
        else:
            if payload is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "unknown_submission",
                        "message": "Unknown submission. Send a SubmissionRef body to register it.",
                    },
                )
            if payload.submission_id != submission_id:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "submission_id_mismatch",
                        "message": "The body's submission_id must match the path.",
                    },
                )
            await coordinator.start(payload)
            response.status_code = status.HTTP_201_CREATED
    except HTTPException:
        raise
    except Exception as error:  # noqa: BLE001 — mapped to HTTP below
        raise _as_http_error(error) from error

    result = await performance.performance_for_submission(db, submission_id)
    if result is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "no_observation_recorded",
                "message": "The reading succeeded but nothing was stored.",
            },
        )
    return result


@router.get("/submissions/{submission_id}/performance", response_model=PerformanceResult)
async def read_performance(
    submission_id: uuid.UUID,
    since_snapshot_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """What we know about a submission, from our tables alone.

    Pass `since_snapshot_id` — the `provenance.snapshot_id` from the last
    response you settled against — to get `features.billable_views`: how
    much this submission has earned since then. Asking twice with the same
    baseline gives the same answer, which is what makes a billing run
    safe to retry (decision D18).
    """
    result = await performance.performance_for_submission(
        db, submission_id, since_snapshot_id=since_snapshot_id
    )
    if result is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={
                "code": "no_observations",
                "message": "No observations recorded for this submission.",
            },
        )
    return result


@router.get("/submissions/{submission_id}/trust", response_model=TrustResult)
async def read_trust(submission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Does this submission's performance look credible, and why.

    Note what this never returns: an instruction. No "block the payout",
    no "ban the creator". It reports what was observed, against which
    threshold, in a sentence a human can read to the creator in a
    dispute. What that costs anyone is the earnings and admin domains'
    decision, not ours.
    """
    result = await TrustService(db).result_for_submission(submission_id)
    if result is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={
                "code": "no_evaluation",
                "message": "No trust evaluation recorded for this submission.",
            },
        )
    return result


@router.post("/submissions/{submission_id}/trust/review", status_code=status.HTTP_201_CREATED)
async def record_review(
    submission_id: uuid.UUID,
    payload: TrustReviewIn,
    db: AsyncSession = Depends(get_db),
):
    """Record what a human concluded — the label-capture endpoint.

    Every row this writes is a future training example, which is why
    `source` is required: a label drawn from our own flagged queue tells
    us about precision and nothing whatsoever about recall. Admin tooling
    should be sending a steady trickle of `random_audit` reviews on
    submissions we called normal.

    The review is attached to the evaluation the reviewer was looking at,
    so the label always keeps the evidence that produced it.
    """
    content_id = await repository.content_id_for_submission(db, submission_id)
    if content_id is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "unknown_submission", "message": "No such submission here."},
        )

    evaluation = await repository.latest_evaluation(db, content_id)
    review = await repository.add_review(
        db,
        TrustReview(
            content_id=content_id,
            evaluation_id=evaluation.id if evaluation else None,
            outcome=payload.outcome,
            source=payload.source,
            reviewer_id=payload.reviewer_id,
            notes=payload.notes,
        ),
    )
    await db.commit()
    return {
        "review_id": str(review.id),
        "evaluation_id": str(evaluation.id) if evaluation else None,
        "outcome": review.outcome.value,
        "source": review.source.value,
    }


@router.get("/trust/rules")
async def read_rules():
    """The thresholds currently in force.

    Exposed so an admin screen can show what the rules actually are
    instead of them becoming folklore that only this file knows.
    """
    return trust.describe()


def _as_http_error(error: Exception) -> HTTPException:
    for error_type, http_status, code in _HTTP_FAILURES:
        if isinstance(error, error_type):
            headers = None
            if isinstance(error, RateLimited) and error.retry_after:
                # Pass the platform's own backoff straight through, so a
                # caller that retries does it no sooner than we would.
                headers = {"Retry-After": str(error.retry_after)}
            return HTTPException(
                http_status, detail={"code": code, "message": str(error)}, headers=headers
            )

    return HTTPException(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"code": "unexpected_error", "message": f"{type(error).__name__}: {error}"},
    )
