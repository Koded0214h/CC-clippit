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

    # An unfunded campaign cannot be opened, however it is asked.
    assert (await api.post(f"/campaigns/{campaign_id}/activate", headers=_auth(org))).status_code == 409

    from tests.http_app import fund_campaign

    await fund_campaign(api, org, campaign_id)
    live = await api.get(f"/campaigns/{campaign_id}", headers=_auth(org))
    assert live.json()["status"] == "active"

    listed = await api.get("/campaigns", headers=_auth(org))
    assert listed.status_code == 200
    assert any(c["id"] == campaign_id for c in listed.json())

    pot = await api.get(f"/campaigns/{campaign_id}/pool", headers=_auth(org))
    assert pot.status_code == 200, pot.text
    body = pot.json()
    assert body["pot"] == 1.5
    assert body["allocated"] == 0
    assert body["remaining"] == 1.5
    assert body["percent_given"] == 0
    assert body["percent_remaining"] == 100
    assert body["submissions_counted"] == 0
