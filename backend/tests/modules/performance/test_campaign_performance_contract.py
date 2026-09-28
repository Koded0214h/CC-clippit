import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.database import Base
from modules.campaigns import models, schemas
from modules.earnings import models as earnings_models  # noqa: F401
from modules.performance.service import attributed_destination


def _campaign_payload(**overrides):
    payload = {
        "title": "Drop day",
        "description": "Creators show the new collection.",
        "platforms": ["tiktok"],
        "pot": 500_000,
        "payout_rule": {"rate_per_1000_views": 500, "min_views_threshold": 1000},
        "performance_metrics": [
            {"metric_type": "comment", "rate_amount": 25, "unit_size": 1},
            {"metric_type": "purchase", "rate_amount": 1000, "unit_size": 1},
        ],
        "conversion_setup": {
            "destination_type": "whatsapp",
            "whatsapp_number": "+234 801 234 5678",
            "attribution_window_days": 30,
        },
    }
    payload.update(overrides)
    return payload


def test_campaign_accepts_selected_engagement_and_conversion_metrics():
    campaign = schemas.CampaignCreate.model_validate(_campaign_payload())
    assert [metric.metric_type.value for metric in campaign.performance_metrics] == ["comment", "purchase"]
    assert campaign.conversion_setup.whatsapp_number == "2348012345678"


def test_conversion_metric_requires_a_destination():
    with pytest.raises(ValidationError, match="conversion tracking"):
        schemas.CampaignCreate.model_validate(_campaign_payload(conversion_setup=None))


def test_legacy_view_campaign_is_upgraded_to_one_metric():
    payload = _campaign_payload()
    payload.pop("performance_metrics")
    payload.pop("conversion_setup")
    campaign = schemas.CampaignCreate.model_validate(payload)
    assert campaign.performance_metrics[0].metric_type.value == "view"
    assert campaign.performance_metrics[0].unit_size == 1000


def test_whatsapp_destination_carries_attribution_reference():
    campaign = models.Campaign(
        id=uuid.uuid4(),
        event_manager_id=uuid.uuid4(),
        slug="drop-day",
        title="Drop day",
        description="New collection",
        expected_views=1,
        platforms=["tiktok"],
        pot_amount=Decimal("500000"),
        conversion_destination_type="whatsapp",
        conversion_destination_url="https://wa.me/2348012345678",
        attribution_window_days=30,
    )
    link = models.AttributionLink(
        campaign_id=campaign.id,
        creator_id=uuid.uuid4(),
        token_hash="x" * 64,
        short_code="ABCD1234",
        destination_url=campaign.conversion_destination_url,
    )
    destination = attributed_destination(link, campaign)
    assert destination.startswith("https://wa.me/2348012345678?")
    assert "ABCD1234" in destination


def test_performance_tables_are_registered_for_migrations():
    assert {"campaign_metrics", "attribution_links", "performance_events", "metric_earning_accounts"}.issubset(
        Base.metadata.tables
    )
    assert "submission_id" in Base.metadata.tables["metric_earning_accounts"].columns


def test_legacy_metric_backfill_does_not_contain_an_alembic_bind_marker():
    migration = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "d2e7f4a9c1b3_engagement_performance_attribution.py"
    ).read_text(encoding="utf-8")
    assert "':view'" not in migration
    assert "concat(campaign_id::text, chr(58), 'view')" in migration
