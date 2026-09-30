"""End-to-end verification for engagement and conversion campaigns.

These tests never use the application's normal schema. When explicitly
enabled, they create a random Postgres schema, exercise the real FastAPI app,
and remove that schema in ``finally``.
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.database import Base, _asyncpg_url_and_connect_args
from core.deps import get_db
from core.internal_client import get_internal_client
from modules.auth.models import Platform, SocialAccount, User
from modules.campaigns.models import (
    Campaign,
    CampaignIntegration,
    CampaignStatus,
    PerformanceEvent,
)
from modules.earnings.models import EarningEntry, MetricEarningAccount
from modules.earnings.service import settle_submission
from modules.submissions.models import Submission, VerificationStatus
from tests.fakes import FakeIntelligence


pytestmark = pytest.mark.skipif(
    os.getenv("CLIPPIT_REMOTE_PERFORMANCE_TESTS") != "1",
    reason="set CLIPPIT_REMOTE_PERFORMANCE_TESTS=1 to use a disposable Postgres schema",
)


@dataclass
class PerformanceHarness:
    client: httpx.AsyncClient
    sessions: async_sessionmaker[AsyncSession]
    intelligence: FakeIntelligence


def _isolated_postgres_url() -> str:
    """Read only DATABASE_URL from the ignored backend env file.

    ``backend/conftest.py`` intentionally points ordinary pytest collection
    at SQLite. This opt-in suite needs native Postgres types, so it reads the
    configured URL without changing the process-wide test defaults.
    """

    env_path = Path(__file__).resolve().parents[3] / ".env"
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("DATABASE_URL="):
            value = line.split("=", 1)[1].strip()
            if value.startswith("postgresql+asyncpg://"):
                return value
    pytest.skip("backend/.env does not contain a PostgreSQL DATABASE_URL")


@pytest_asyncio.fixture
async def performance_api() -> PerformanceHarness:
    """Real API and Postgres types, isolated from every non-test table."""

    from main import app

    schema = f"clippit_test_performance_{uuid.uuid4().hex[:12]}"
    assert re.fullmatch(r"clippit_test_performance_[0-9a-f]{12}", schema)

    clean_url, base_args = _asyncpg_url_and_connect_args(_isolated_postgres_url())
    admin_engine = create_async_engine(clean_url, connect_args=base_args)
    test_engine = None
    try:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))

        test_engine = create_async_engine(
            clean_url,
            connect_args=base_args,
            execution_options={"schema_translate_map": {None: schema}},
        )
        async with test_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        sessions = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

        async def _db():
            async with sessions() as session:
                yield session

        intelligence = FakeIntelligence()
        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[get_internal_client] = lambda: intelligence
        if hasattr(app.state, "limiter"):
            app.state.limiter.enabled = False

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield PerformanceHarness(client, sessions, intelligence)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_internal_client, None)
        if test_engine is not None:
            await test_engine.dispose()
        async with admin_engine.begin() as connection:
            assert schema.startswith("clippit_test_performance_")
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin_engine.dispose()


def _auth(account: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {account['access_token']}"}


async def _signup_verified(harness: PerformanceHarness, role: str) -> dict:
    email = f"performance-{role}-{uuid.uuid4().hex[:8]}@example.com"
    response = await harness.client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "DemoPassword123!",
            "full_name": f"Performance {role}",
            "role": role,
        },
    )
    response.raise_for_status()
    account = response.json()
    async with harness.sessions() as session:
        user = await session.get(User, uuid.UUID(account["user"]["id"]))
        assert user is not None
        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc)
        await session.commit()
    return account


async def _submit_and_approve(
    harness: PerformanceHarness,
    organisation: dict,
    creator: dict,
    campaign_id: str,
    suffix: str,
) -> str:
    response = await harness.client.post(
        "/submissions",
        headers=_auth(creator),
        json={
            "campaign_id": campaign_id,
            "platform": "tiktok",
            "url": f"https://www.tiktok.com/@performance/video/{suffix}",
            "title": f"Performance clip {suffix}",
        },
    )
    response.raise_for_status()
    submission_id = response.json()["id"]
    async with harness.sessions() as session:
        submission = await session.get(Submission, uuid.UUID(submission_id))
        assert submission is not None
        already_approved = submission.verification_status == VerificationStatus.approved
    if not already_approved:
        approved = await harness.client.post(
            f"/brand/reviews/{submission_id}/approve",
            headers=_auth(organisation),
            json={},
        )
        approved.raise_for_status()
    return submission_id


async def test_hybrid_campaign_tracking_settlement_and_isolation(performance_api: PerformanceHarness):
    harness = performance_api
    tracker = await harness.client.get("/tracker.js")
    assert tracker.status_code == 200
    assert tracker.headers["content-type"].startswith("application/javascript")
    assert "window.ClippitTracking" in tracker.text
    assert "clippit_ref" in tracker.text

    organisation = await _signup_verified(harness, "organisation")
    creator = await _signup_verified(harness, "creator")

    creator_id = creator["user"]["id"]
    async with harness.sessions() as session:
        session.add(
            SocialAccount(
                user_id=uuid.UUID(creator_id),
                platform=Platform.tiktok,
                platform_user_id=f"performance-{uuid.uuid4().hex[:8]}",
                handle="@performance_creator",
                display_name="Performance Creator",
                access_token="test-token",
            )
        )
        await session.commit()

    metrics = [
        {"metric_type": "view", "rate_amount": 500, "unit_size": 1000, "min_threshold": 0},
        {"metric_type": "comment", "rate_amount": 25, "unit_size": 1, "min_threshold": 0},
        {"metric_type": "share", "rate_amount": 40, "unit_size": 1, "min_threshold": 0},
        {"metric_type": "visit", "rate_amount": 15, "unit_size": 1, "min_threshold": 0},
        {"metric_type": "signup", "rate_amount": 250, "unit_size": 1, "min_threshold": 0},
        {"metric_type": "purchase", "rate_amount": 1000, "unit_size": 1, "min_threshold": 0},
    ]
    created = await harness.client.post(
        "/campaigns",
        headers=_auth(organisation),
        json={
            "title": "Verified outcomes",
            "description": "A complete engagement and conversion campaign test.",
            "platforms": ["tiktok"],
            "pot": 500_000,
            "payout_rule": {
                "rate_per_1000_views": 500,
                "min_views_threshold": 0,
                "max_submissions": 3,
            },
            "performance_metrics": metrics,
            "conversion_setup": {
                "destination_type": "website",
                "destination_url": "https://shop.example/products?id=42",
                "attribution_window_days": 30,
                "attribution_model": "last_touch",
            },
        },
    )
    created.raise_for_status()
    campaign_id = created.json()["id"]

    setup_before_key = await harness.client.get(
        f"/campaigns/{campaign_id}/integration", headers=_auth(organisation)
    )
    setup_before_key.raise_for_status()
    assert setup_before_key.json()["configured"] is False
    assert set(setup_before_key.json()["selected_event_types"]) == {"visit", "signup", "purchase"}

    async with harness.sessions() as session:
        campaign = await session.get(Campaign, uuid.UUID(campaign_id))
        assert campaign is not None
        campaign.status = CampaignStatus.active
        campaign.activated_at = datetime.now(timezone.utc)
        await session.commit()

    joined = await harness.client.post(
        f"/campaigns/{campaign_id}/join", headers=_auth(creator), json={}
    )
    joined.raise_for_status()

    first_submission = await _submit_and_approve(
        harness, organisation, creator, campaign_id, "100000000001"
    )
    first_link = await harness.client.post(
        f"/campaigns/{campaign_id}/attribution-links",
        headers=_auth(creator),
        json={"submission_id": first_submission},
    )
    first_link.raise_for_status()
    first_link_body = first_link.json()
    token_path = urlsplit(first_link_body["tracking_url"]).path

    invalid_token = await harness.client.get("/t/not-a-real-token", follow_redirects=False)
    assert invalid_token.status_code == 404

    followed = await harness.client.get(
        token_path,
        headers={"User-Agent": "performance-suite"},
        follow_redirects=False,
    )
    assert followed.status_code == 307
    destination = urlsplit(followed.headers["location"])
    destination_query = parse_qs(destination.query)
    assert destination.netloc == "shop.example"
    assert destination_query["id"] == ["42"]
    assert destination_query["clippit_ref"] == [first_link_body["short_code"]]

    duplicate_visit = await harness.client.get(
        token_path,
        headers={"User-Agent": "performance-suite"},
        follow_redirects=False,
    )
    assert duplicate_visit.status_code == 307

    integration = await harness.client.post(
        f"/campaigns/{campaign_id}/integration-secret",
        headers=_auth(organisation),
        json={},
    )
    integration.raise_for_status()
    secret = integration.json()["secret"]

    setup_after_key = await harness.client.get(
        f"/campaigns/{campaign_id}/integration", headers=_auth(organisation)
    )
    setup_after_key.raise_for_status()
    assert setup_after_key.json()["configured"] is True
    assert setup_after_key.json()["secret_last_four"] == secret[-4:]

    event_base = {
        "campaign_id": campaign_id,
        "attribution_code": first_link_body["short_code"],
        "quantity": 1,
    }
    wrong_secret = await harness.client.post(
        "/performance/events",
        headers={"X-Clippit-Secret": "wrong-secret"},
        json={**event_base, "event_type": "signup", "source_event_id": "signup-wrong"},
    )
    assert wrong_secret.status_code == 401

    unselected = await harness.client.post(
        "/performance/events",
        headers={"X-Clippit-Secret": secret},
        json={**event_base, "event_type": "lead", "source_event_id": "lead-1"},
    )
    assert unselected.status_code == 422

    social_event = await harness.client.post(
        "/performance/events",
        headers={"X-Clippit-Secret": secret},
        json={**event_base, "event_type": "comment", "source_event_id": "comment-1"},
    )
    assert social_event.status_code == 422

    signup = await harness.client.post(
        "/performance/events",
        headers={"X-Clippit-Secret": secret},
        json={**event_base, "event_type": "signup", "source_event_id": "signup-1"},
    )
    signup.raise_for_status()
    purchase = await harness.client.post(
        "/performance/events",
        headers={"X-Clippit-Secret": secret},
        json={
            **event_base,
            "event_type": "purchase",
            "source_event_id": "order-1",
            "value_amount": 35_000,
            "currency": "NGN",
        },
    )
    purchase.raise_for_status()
    repeated_purchase = await harness.client.post(
        "/performance/events",
        headers={"X-Clippit-Secret": secret},
        json={
            **event_base,
            "event_type": "purchase",
            "source_event_id": "order-1",
            "value_amount": 35_000,
            "currency": "NGN",
        },
    )
    repeated_purchase.raise_for_status()
    assert repeated_purchase.json()["id"] == purchase.json()["id"]

    harness.intelligence.set_performance(first_submission, views=2500, comments=4, shares=3)
    async with harness.sessions() as session:
        await settle_submission(session, uuid.UUID(first_submission), harness.intelligence)
        await session.commit()

    second_submission = await _submit_and_approve(
        harness, organisation, creator, campaign_id, "100000000002"
    )
    harness.intelligence.set_performance(second_submission, views=1000, comments=1, shares=2)
    second_link = await harness.client.post(
        f"/campaigns/{campaign_id}/attribution-links",
        headers=_auth(creator),
        json={"submission_id": second_submission},
    )
    second_link.raise_for_status()
    second_body = second_link.json()
    second_path = urlsplit(second_body["tracking_url"]).path
    second_visit = await harness.client.get(
        second_path,
        headers={"User-Agent": "performance-suite-second"},
        follow_redirects=False,
    )
    assert second_visit.status_code == 307
    second_purchase = await harness.client.post(
        "/performance/events",
        headers={"X-Clippit-Secret": secret},
        json={
            "campaign_id": campaign_id,
            "event_type": "purchase",
            "attribution_code": second_body["short_code"],
            "source_event_id": "order-2",
            "quantity": 1,
            "value_amount": 20_000,
            "currency": "NGN",
        },
    )
    second_purchase.raise_for_status()
    async with harness.sessions() as session:
        await settle_submission(session, uuid.UUID(second_submission), harness.intelligence)
        await settle_submission(session, uuid.UUID(first_submission), harness.intelligence)
        await session.commit()

    summary = await harness.client.get(
        f"/campaigns/{campaign_id}/performance", headers=_auth(organisation)
    )
    summary.raise_for_status()
    totals = {row["metric_type"]: row for row in summary.json()["metrics"]}
    assert totals["view"]["approved"] == 3500
    assert totals["comment"]["approved"] == 5
    assert totals["share"]["approved"] == 5
    assert totals["visit"]["approved"] == 2
    assert totals["signup"]["approved"] == 1
    assert totals["purchase"]["approved"] == 2

    creator_summary = await harness.client.get(
        f"/campaigns/{campaign_id}/performance", headers=_auth(creator)
    )
    creator_summary.raise_for_status()
    assert creator_summary.json() == summary.json()

    async with harness.sessions() as session:
        earning_rows = await session.execute(
            select(EarningEntry.metric_type, func.sum(EarningEntry.amount))
            .where(EarningEntry.campaign_id == uuid.UUID(campaign_id))
            .group_by(EarningEntry.metric_type)
        )
        earnings = {metric: Decimal(amount) for metric, amount in earning_rows}
        assert earnings == {
            "view": Decimal("1500.00"),
            "comment": Decimal("125.00"),
            "share": Decimal("200.00"),
            "visit": Decimal("30.00"),
            "signup": Decimal("250.00"),
            "purchase": Decimal("2000.00"),
        }
        assert sum(earnings.values()) == Decimal("4105.00")

        cursor_rows = list(
            await session.scalars(
                select(MetricEarningAccount).where(
                    MetricEarningAccount.campaign_id == uuid.UUID(campaign_id)
                )
            )
        )
        assert len(cursor_rows) == 12
        assert {row.submission_id for row in cursor_rows} == {
            uuid.UUID(first_submission),
            uuid.UUID(second_submission),
        }

        references = list(
            await session.scalars(
                select(EarningEntry.reference).where(
                    EarningEntry.campaign_id == uuid.UUID(campaign_id)
                )
            )
        )
        assert len(references) == len(set(references))

        visits = list(
            await session.scalars(
                select(PerformanceEvent).where(
                    PerformanceEvent.campaign_id == uuid.UUID(campaign_id),
                    PerformanceEvent.event_type == "visit",
                )
            )
        )
        assert len(visits) == 3
        assert sum(event.fraud_status == "suspicious" for event in visits) == 1

        stored_integration = await session.get(CampaignIntegration, uuid.UUID(campaign_id))
        assert stored_integration is not None
        assert stored_integration.secret_hash != secret
        assert len(stored_integration.secret_hash) == 64

    rotated = await harness.client.post(
        f"/campaigns/{campaign_id}/integration-secret",
        headers=_auth(organisation),
        json={},
    )
    rotated.raise_for_status()
    rotated_secret = rotated.json()["secret"]
    assert rotated_secret != secret

    stale_key = await harness.client.post(
        "/performance/events",
        headers={"X-Clippit-Secret": secret},
        json={**event_base, "event_type": "signup", "source_event_id": "signup-stale"},
    )
    assert stale_key.status_code == 401
    current_key_duplicate = await harness.client.post(
        "/performance/events",
        headers={"X-Clippit-Secret": rotated_secret},
        json={**event_base, "event_type": "purchase", "source_event_id": "order-1"},
    )
    current_key_duplicate.raise_for_status()
    assert current_key_duplicate.json()["id"] == purchase.json()["id"]
