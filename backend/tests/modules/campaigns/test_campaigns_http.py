from tests.http_app import api, signup  # noqa: F401


def _auth(body: dict) -> dict:
    return {"Authorization": f"Bearer {body['access_token']}"}


async def test_organisation_creates_and_activates_a_campaign(api):
    _, org = await signup(api, "organisation")
    created = await api.post(
        "/campaigns",
        headers=_auth(org),
        json={
            "title": "Sprint campaign",
            "description": "HTTP test",
            "expected_views": 1000,
            "platforms": ["tiktok"],
            "payout_rule": {"rate_per_1000_views": 1.5, "min_views_threshold": 0},
        },
    )
    assert created.status_code == 201, created.text
    campaign_id = created.json()["id"]

    activated = await api.post(f"/campaigns/{campaign_id}/activate", headers=_auth(org))
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"

    listed = await api.get("/campaigns", headers=_auth(org))
    assert listed.status_code == 200
    assert any(c["id"] == campaign_id for c in listed.json())
