"""Joining and leaving a campaign — explicit, and ahead of submitting a
clip (production-api-inventory.md §G). Also covers the null-`duration_days`
bug fix: no deadline must mean no deadline, not a silent 14-day one."""

import pytest

from tests.http_app import api, approve_clip, auth, campaign_body, fund_campaign, intel, make_creator, signup, submit_clip


async def test_a_creator_joins_before_submitting_and_the_badge_follows(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)

    joined = await api.post(f"/campaigns/{campaign['id']}/join", headers=auth(creator))
    assert joined.status_code == 201
    body = joined.json()
    assert body["campaign_id"] == campaign["id"] and body["left_at"] is None

    card = (await api.get(f"/campaigns/{campaign['id']}", headers=auth(creator))).json()
    assert card["joined"] is True and card["feed_status"] == "Joined"

    feed = (await api.get("/campaigns", headers=auth(creator), params={"feed": "joined"})).json()
    assert [c["id"] for c in feed] == [campaign["id"]]
    open_feed = (await api.get("/campaigns", headers=auth(creator), params={"feed": "open"})).json()
    assert campaign["id"] not in [c["id"] for c in open_feed]


async def test_joining_twice_is_the_same_membership(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)

    first = (await api.post(f"/campaigns/{campaign['id']}/join", headers=auth(creator))).json()
    second = (await api.post(f"/campaigns/{campaign['id']}/join", headers=auth(creator))).json()
    assert first["id"] == second["id"]


async def test_joining_needs_a_connected_platform(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body(platforms=["instagram"]))).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api, platform="tiktok")  # wrong platform for this campaign

    r = await api.post(f"/campaigns/{campaign['id']}/join", headers=auth(creator))
    assert r.status_code == 409


async def test_leaving_before_a_clip_is_accepted_is_fine_but_not_after(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    await api.post(f"/campaigns/{campaign['id']}/join", headers=auth(creator))

    left = await api.delete(f"/campaigns/{campaign['id']}/join", headers=auth(creator))
    assert left.status_code == 200 and left.json()["left_at"] is not None

    # Rejoin, submit, get approved: now leaving is refused.
    await api.post(f"/campaigns/{campaign['id']}/join", headers=auth(creator))
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await approve_clip(api, org, sid)
    blocked = await api.delete(f"/campaigns/{campaign['id']}/join", headers=auth(creator))
    assert blocked.status_code == 409


async def test_leaving_without_having_joined_is_404(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    r = await api.delete(f"/campaigns/{campaign['id']}/join", headers=auth(creator))
    assert r.status_code == 404


async def test_my_campaigns_lists_joined_submitted_and_left(api, intel):
    _, org = await signup(api, "organisation")
    joined_only = (await api.post("/campaigns", headers=auth(org), json=campaign_body(title="Joined only"))).json()
    submitted = (
        await api.post(
            "/campaigns",
            headers=auth(org),
            json=campaign_body(title="Submitted", rules=[{"kind": "must", "text": "Say the brand name out loud"}]),
        )
    ).json()
    left = (await api.post("/campaigns", headers=auth(org), json=campaign_body(title="Left"))).json()
    for c in (joined_only, submitted, left):
        await fund_campaign(api, org, c["id"])
    creator = await make_creator(api)

    await api.post(f"/campaigns/{joined_only['id']}/join", headers=auth(creator))
    await submit_clip(api, creator, submitted["id"])
    await api.post(f"/campaigns/{left['id']}/join", headers=auth(creator))
    await api.delete(f"/campaigns/{left['id']}/join", headers=auth(creator))

    rows = (await api.get("/creators/me/campaigns", headers=auth(creator))).json()
    by_title = {r["campaign"]["title"]: r for r in rows}
    assert by_title["Joined only"]["membership_status"] == "joined"
    assert by_title["Submitted"]["membership_status"] == "submitted"
    assert by_title["Submitted"]["submission_id"] is not None
    assert by_title["Left"]["membership_status"] == "left"

    only_left = (await api.get("/creators/me/campaigns", headers=auth(creator), params={"membership_status": "left"})).json()
    assert [r["campaign"]["title"] for r in only_left] == ["Left"]


async def test_an_organisation_cannot_join_a_campaign(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    r = await api.post(f"/campaigns/{campaign['id']}/join", headers=auth(org))
    assert r.status_code == 403


async def test_a_campaign_with_no_duration_never_gets_a_deadline(api, intel):
    """The explicit end-condition bug from production-api-inventory.md: null
    `duration_days` must mean no calendar deadline, not a silent default."""
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body(duration_days=None))).json()
    assert campaign["duration_days"] is None
    funded = await fund_campaign(api, org, campaign["id"])
    assert funded["ends_at"] is None if "ends_at" in funded else True
    live = (await api.get(f"/campaigns/{campaign['id']}", headers=auth(org))).json()
    assert live["status"] == "active" and live["ends_at"] is None and live["time_left"] is None


async def test_a_campaign_with_a_duration_still_gets_one(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body(duration_days=7))).json()
    await fund_campaign(api, org, campaign["id"])
    live = (await api.get(f"/campaigns/{campaign['id']}", headers=auth(org))).json()
    assert live["ends_at"] is not None and live["time_left"]["days"] <= 7
