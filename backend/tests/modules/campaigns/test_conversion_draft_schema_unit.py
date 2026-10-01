import pytest
from pydantic import ValidationError

from modules.campaigns.schemas import CampaignDraftPatch, ConversionSetup


def test_website_conversion_draft_accepts_an_unfinished_url():
    draft = CampaignDraftPatch(
        revision=0,
        conversion_setup={
            "destination_type": "website",
            "destination_url": "https://",
            "attribution_window_days": 30,
            "attribution_model": "first_touch",
        },
    )

    assert draft.conversion_setup is not None
    assert draft.conversion_setup.destination_url == "https://"
    assert draft.conversion_setup.attribution_model == "first_touch"


def test_completed_campaign_still_requires_a_real_website_url():
    with pytest.raises(ValidationError):
        ConversionSetup(destination_type="website", destination_url="https://")


def test_brand_cannot_replace_the_first_creator_attribution_rule():
    setup = ConversionSetup(
        destination_type="website",
        destination_url="https://shop.example.com",
        attribution_model="last_touch",
    )

    assert setup.attribution_model == "first_touch"
