"""The boundary, exercised over HTTP exactly as Koded's code will.

Two things are being checked here that no unit test can: that every
failure mode arrives as a status code with a machine-readable `code`
rather than a 500 and a stack trace, and that nothing platform-shaped
(raw payloads, provider vocabulary, internal errors) gets out.

The app is assembled per test with just this module's router, so these
tests don't depend on auth, the rate limiter, or anything else in
`main.py` being importable.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest_asyncio
from fastapi import FastAPI

from core.config import get_settings
from core.deps import get_db
from core.platforms import Platform
from integrations.social.base import (
    CommentPage,
    ContentKind,
    ContentUnavailable,
    PlatformContent,
    PlatformMetrics,
    PostType,
    RateLimited,
)
from modules.intelligence.ingestion import IngestionService
from modules.intelligence.internal_router import get_coordinator, router
from modules.intelligence.polling import PollingCoordinator
from modules.intelligence.tokens import StaticTokenSource

T0 = datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc)
CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
CAMPAIGN_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
VIDEO_ID = "7401234567890123456"
SECRET = {"X-Internal-Secret": get_settings().internal_service_secret}


class StubPlatform:
    platform = Platform.tiktok
    source = "tiktok.display_api"
    requires_creator_token = True
    supports_comments = False

    def __init__(self, clock) -> None:
        self._clock = clock
        self.views = 1000
        self.error: Exception | None = None
        self.resolves = True
        self.metrics_calls = 0

    async def resolve_url(self, url: str) -> str | None:
        return VIDEO_ID if self.resolves else None

    async def get_content(self, content_id: str, *, access_token: str | None = None):
        return PlatformContent(
            platform=Platform.tiktok,
            platform_content_id=content_id,
            url=f"https://www.tiktok.com/@creator/video/{content_id}",
            author_username="creator",
            kind=ContentKind.video,
            post_type=PostType.original,
            published_at=T0 - timedelta(hours=2),
            raw={"secret_provider_field": "must not escape"},
        )

    async def get_metrics(self, content_id: str, *, access_token: str | None = None):
        self.metrics_calls += 1
        if self.error:
            raise self.error
        return PlatformMetrics(
            platform=Platform.tiktok,
            platform_content_id=content_id,
            observed_at=self._clock(),
            views=self.views,
            likes=80,
            comments=12,
            shares=4,
            raw={"another_provider_field": "must not escape"},
        )

    async def get_comments(self, content_id: str, *, access_token=None, cursor=None) -> CommentPage:
        raise AssertionError("not used")


class FakeClock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest_asyncio.fixture
async def api(session_factory):
    clock = FakeClock()
    platform = StubPlatform(clock)
    tokens = StaticTokenSource({(CREATOR_ID, Platform.tiktok): "creator-token"})

    def ingestion_factory(session):
        return IngestionService(
            session, token_source=tokens, adapter_lookup=lambda _: platform
        )

    coordinator = PollingCoordinator(
        session_factory, ingestion_factory=ingestion_factory, clock=clock, concurrency=1
    )

    app = FastAPI()
    app.include_router(router)

    async def _db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_coordinator] = lambda: coordinator

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", headers=SECRET
    ) as client:
        yield SimpleNamespace(
            client=client, clock=clock, platform=platform, tokens=tokens, coordinator=coordinator
        )


def _ref(submission_id: uuid.UUID) -> dict:
    return {
        "submission_id": str(submission_id),
        "campaign_id": str(CAMPAIGN_ID),
        "creator_id": str(CREATOR_ID),
        "platform": "tiktok",
        "url": f"https://www.tiktok.com/@creator/video/{VIDEO_ID}",
    }


async def _register(api, submission_id: uuid.UUID | None = None) -> tuple[uuid.UUID, dict]:
    submission_id = submission_id or uuid.uuid4()
    response = await api.client.post(
        f"/internal/submissions/{submission_id}/metrics", json=_ref(submission_id)
    )
    assert response.status_code == 201, response.text
    return submission_id, response.json()


async def test_registering_a_submission_takes_a_first_reading(api):
    _, body = await _register(api)

    assert body["metrics"]["views"] == 1000
    assert body["features"]["observation_count"] == 1
    assert body["features"]["incremental_views"] is None, "one point is not a trend"
    assert body["provenance"]["source"] == "tiktok.display_api"
    assert body["provenance"]["snapshot_id"]
    assert body["tracking"]["status"] == "active"
    assert body["content"]["post_type"] == "original"


async def test_a_later_reading_reports_growth(api):
    submission_id, _ = await _register(api)

    api.clock.advance(timedelta(hours=1))
    api.platform.views = 1600
    body = (await api.client.post(f"/internal/submissions/{submission_id}/metrics")).json()

    assert body["metrics"]["views"] == 1600
    assert body["features"]["observation_count"] == 2
    assert body["features"]["incremental_views"] == 600
    assert body["features"]["view_velocity_per_hour"] == 600.0


async def test_reading_performance_never_touches_a_platform(api):
    """A billing run must not be slow, throttled, or wrong because TikTok
    is having a bad day."""
    submission_id, _ = await _register(api)
    calls_after_registering = api.platform.metrics_calls

    response = await api.client.get(f"/internal/submissions/{submission_id}/performance")

    assert response.status_code == 200
    assert api.platform.metrics_calls == calls_after_registering


async def test_billable_views_are_measured_from_the_snapshot_the_caller_settled(api):
    """The exit condition for this stage: earnings can compute what it owes
    from our responses alone, and get the same answer if it asks twice."""
    submission_id, first = await _register(api)
    settled_at = first["provenance"]["snapshot_id"]

    api.clock.advance(timedelta(hours=1))
    api.platform.views = 1600
    await api.client.post(f"/internal/submissions/{submission_id}/metrics")
    api.clock.advance(timedelta(hours=1))
    api.platform.views = 2500
    await api.client.post(f"/internal/submissions/{submission_id}/metrics")

    url = f"/internal/submissions/{submission_id}/performance?since_snapshot_id={settled_at}"
    first_read = (await api.client.get(url)).json()
    second_read = (await api.client.get(url)).json()

    assert first_read["features"]["billable_views"] == 1500
    assert second_read["features"]["billable_views"] == 1500
    assert first_read["metrics"]["views"] == 2500, "the cumulative total is always the latest"


async def test_without_a_baseline_no_billable_figure_is_offered(api):
    """Only the caller knows what it has already paid for, so guessing
    would be worse than saying nothing."""
    submission_id, _ = await _register(api)

    body = (await api.client.get(f"/internal/submissions/{submission_id}/performance")).json()

    assert body["features"]["billable_views"] is None


async def test_a_baseline_from_a_different_post_is_refused(api):
    """Cross-wiring two submissions' snapshots would produce a plausible
    number that is completely wrong — the worst kind."""
    _, other = await _register(api)
    submission_id, _ = await _register(api)

    url = (
        f"/internal/submissions/{submission_id}/performance"
        f"?since_snapshot_id={other['provenance']['snapshot_id']}"
    )
    body = (await api.client.get(url)).json()

    assert body["features"]["billable_views"] is None


async def test_an_unreadable_url_is_a_422_with_a_code_not_a_500(api):
    api.platform.resolves = False
    submission_id = uuid.uuid4()

    response = await api.client.post(
        f"/internal/submissions/{submission_id}/metrics", json=_ref(submission_id)
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "url_not_recognised"


async def test_a_disconnected_creator_gets_a_409_telling_the_caller_why(api):
    api.tokens = None
    submission_id = uuid.uuid4()
    # Same coordinator, but the creator has no token configured.
    ref = _ref(submission_id)
    ref["creator_id"] = str(uuid.uuid4())

    response = await api.client.post(f"/internal/submissions/{submission_id}/metrics", json=ref)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "creator_reconnect_required"


async def test_rate_limiting_passes_the_providers_own_backoff_through(api):
    """If we tell a caller to retry sooner than the platform told us, we've
    just moved the throttle downstream."""
    api.platform.error = RateLimited("slow down", retry_after=42)
    submission_id = uuid.uuid4()

    response = await api.client.post(
        f"/internal/submissions/{submission_id}/metrics", json=_ref(submission_id)
    )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "42"
    assert response.json()["detail"]["code"] == "rate_limited"


async def test_a_failed_re_observation_is_reported_as_state_not_as_an_error(api):
    """Registration fails loudly because someone is waiting. A later poll
    failing is operational: the submission exists, its numbers are still
    valid, and `tracking` says why they stopped moving."""
    submission_id, _ = await _register(api)

    api.platform.error = ContentUnavailable("the creator made the post private")
    api.clock.advance(timedelta(hours=1))
    response = await api.client.post(f"/internal/submissions/{submission_id}/metrics")

    assert response.status_code == 200
    tracking = response.json()["tracking"]
    assert tracking["status"] == "stopped"
    assert tracking["reason_code"] == "content_unavailable"


async def test_posting_without_a_body_for_an_unknown_submission_says_what_to_do(api):
    response = await api.client.post(f"/internal/submissions/{uuid.uuid4()}/metrics")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "unknown_submission"


async def test_a_body_that_disagrees_with_the_path_is_rejected(api):
    response = await api.client.post(
        f"/internal/submissions/{uuid.uuid4()}/metrics", json=_ref(uuid.uuid4())
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "submission_id_mismatch"


async def test_an_unknown_submission_has_no_performance(api):
    response = await api.client.get(f"/internal/submissions/{uuid.uuid4()}/performance")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "no_observations"


async def test_the_internal_secret_is_required(api):
    response = await api.client.get(
        f"/internal/submissions/{uuid.uuid4()}/performance", headers={"X-Internal-Secret": "wrong"}
    )

    assert response.status_code == 401


async def test_trust_is_evaluated_alongside_every_reading(api):
    """A stored observation is never readable without a verdict attached,
    because they're written in the same transaction."""
    submission_id, _ = await _register(api)

    response = await api.client.get(f"/internal/submissions/{submission_id}/trust")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_data", "one reading is not enough to judge"
    assert body["signals"] == []
    assert 0.0 <= body["anomaly_score"] <= 1.0


async def test_a_flag_arrives_with_an_explanation_a_human_can_read(api):
    """Stage 5's exit condition, over the wire."""
    submission_id, _ = await _register(api)

    for hours, views in ((1, 1200), (2, 1400), (3, 90_000)):
        api.clock.advance(timedelta(hours=1))
        api.platform.views = views
        await api.client.post(f"/internal/submissions/{submission_id}/metrics")

    body = (await api.client.get(f"/internal/submissions/{submission_id}/trust")).json()

    assert body["status"] == "flagged"
    assert body["signals"], "a flag with no stated reason is not defensible"
    signal = body["signals"][0]
    assert {"code", "severity", "explanation", "observed_value", "threshold"} <= set(signal)
    assert signal["threshold"] is not None


async def test_trust_says_nothing_about_money(api):
    """This module reports what it sees. Whether a flag withholds a
    payout belongs to earnings and admin, and the response shape should
    make that impossible to confuse."""
    submission_id, _ = await _register(api)

    body = (await api.client.get(f"/internal/submissions/{submission_id}/trust")).json()

    assert set(body) == {
        "submission_id",
        "status",
        "anomaly_score",
        "signals",
        "evaluated_at",
        "comments_sampled",
    }
    assert body["comments_sampled"] == 0


async def test_a_human_verdict_can_be_recorded_against_the_evidence(api):
    submission_id, _ = await _register(api)

    response = await api.client.post(
        f"/internal/submissions/{submission_id}/trust/review",
        json={
            "outcome": "legitimate",
            "source": "random_audit",
            "reviewer_id": str(uuid.uuid4()),
            "notes": "Checked the account manually; looks like a real creator.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["evaluation_id"], "a label must keep the evaluation it was made against"
    assert body["source"] == "random_audit"


async def test_a_review_needs_a_source(api):
    """Without knowing why a submission reached a reviewer, the label
    can't be used to measure anything."""
    submission_id, _ = await _register(api)

    response = await api.client.post(
        f"/internal/submissions/{submission_id}/trust/review",
        json={"outcome": "legitimate", "reviewer_id": str(uuid.uuid4())},
    )

    assert response.status_code == 422


async def test_the_active_thresholds_are_inspectable(api):
    """So the rules are visible to an admin instead of being folklore
    only the source file knows."""
    body = (await api.client.get("/internal/trust/rules")).json()

    assert body["velocity_spike_multiple"]
    assert body["min_like_view_ratio"]["tiktok"]


async def test_no_provider_payload_escapes_the_boundary(api):
    """`raw` is kept on every stored row for diagnosis, and must never be
    part of what another module reads."""
    submission_id, body = await _register(api)
    serialized = (
        await api.client.get(f"/internal/submissions/{submission_id}/performance")
    ).text

    for leak in ("secret_provider_field", "another_provider_field", "raw_metrics", "raw_content"):
        assert leak not in serialized
    assert set(body) == {"submission_id", "content", "metrics", "features", "provenance", "tracking"}


async def test_core_can_stop_and_resume_tracking(api):
    """Withdraw / campaign close must actually stop polling (D17)."""
    submission_id, _ = await _register(api)

    stopped = await api.client.post(f"/internal/submissions/{submission_id}/tracking/stop")
    assert stopped.status_code == 200
    assert stopped.json() == {"stopped": True}

    after_stop = (
        await api.client.get(f"/internal/submissions/{submission_id}/performance")
    ).json()
    assert after_stop["tracking"]["status"] == "stopped"

    resumed = await api.client.post(f"/internal/submissions/{submission_id}/tracking/resume")
    assert resumed.status_code == 200
    assert resumed.json() == {"resumed": True}

    after_resume = (
        await api.client.get(f"/internal/submissions/{submission_id}/performance")
    ).json()
    assert after_resume["tracking"]["status"] == "active"
