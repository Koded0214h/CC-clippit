from tests.http_app import api, signup  # noqa: F401


def _auth(body: dict) -> dict:
    return {"Authorization": f"Bearer {body['access_token']}"}


async def _active_campaign(api) -> tuple[dict, str]:
    _, org = await signup(api, "organisation")
    created = await api.post(
        "/campaigns",
        headers=_auth(org),
        json={
            "title": "Submit here",
            "description": "HTTP test",
            "expected_views": 1000,
            "platforms": ["tiktok"],
            "payout_rule": {"rate_per_1000_views": 1.5, "min_views_threshold": 0},
        },
    )
    campaign_id = created.json()["id"]
    from tests.http_app import fund_campaign

    await fund_campaign(api, org, campaign_id)
    return org, campaign_id


async def test_submit_without_connected_account_is_conflict(api):
    _, campaign_id = await _active_campaign(api)
    _, creator = await signup(api, "creator")
    r = await api.post(
        "/submissions",
        headers=_auth(creator),
        json={
            "campaign_id": campaign_id,
            "platform": "tiktok",
            "url": "https://www.tiktok.com/@x/video/1",
        },
    )
    assert r.status_code == 409
    assert "Connect" in r.json()["detail"]


async def test_withdraw_unknown_submission_is_not_found(api):
    _, creator = await signup(api, "creator")
    r = await api.post(
        "/submissions/00000000-0000-0000-0000-000000000001/withdraw",
        headers=_auth(creator),
    )
    assert r.status_code == 404
