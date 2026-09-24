"""PRD V1's campaign builder additions: access mode / invite codes, assets,
end condition, per-video cap, max submissions, and full-freeze pause."""

from tests.http_app import (
    api, approve_clip, auth, campaign_body, clear_hold, earn, fund_campaign, intel, make_creator, open_campaign,
    signup, submit_clip,
)


# --- access mode / invite codes -----------------------------------------------------------------


async def test_a_public_campaign_needs_no_code_to_join(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    assert campaign["access_mode"] == "public" and campaign["invite_code"] is None
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    assert (await api.post(f"/campaigns/{campaign['id']}/join", headers=auth(creator))).status_code == 201


async def test_an_invite_campaign_needs_the_right_code(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body(access_mode="invite"))).json()
    assert campaign["access_mode"] == "invite" and campaign["invite_code"]
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)

    no_code = await api.post(f"/campaigns/{campaign['id']}/join", headers=auth(creator))
    assert no_code.status_code == 403

    wrong = await api.post(f"/campaigns/{campaign['id']}/join", headers=auth(creator), params={"invite_code": "NOPE0000"})
    assert wrong.status_code == 403

    right = await api.post(
        f"/campaigns/{campaign['id']}/join", headers=auth(creator), params={"invite_code": campaign["invite_code"].lower()}
    )
    assert right.status_code == 201  # case-insensitive


async def test_the_invite_code_is_hidden_from_creators(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body(access_mode="invite"))).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    seen_by_creator = (await api.get(f"/campaigns/{campaign['id']}", headers=auth(creator))).json()
    assert seen_by_creator["invite_code"] is None
    seen_by_owner = (await api.get(f"/campaigns/{campaign['id']}", headers=auth(org))).json()
    assert seen_by_owner["invite_code"] == campaign["invite_code"]


# --- assets and end condition ---------------------------------------------------------------------


async def test_assets_and_end_condition_round_trip(api, intel):
    _, org = await signup(api, "organisation")
    assets = [{"name": "Campaign sound", "url": "https://cdn.example.com/sound.mp3", "kind": "sound"}]
    campaign = (
        await api.post(
            "/campaigns", headers=auth(org),
            json=campaign_body(assets=assets, end_condition="budget", duration_days=None, expected_views=1000),
        )
    ).json()
    assert campaign["assets"] == assets and campaign["end_condition"] == "budget"


async def test_end_condition_defaults_from_duration(api, intel):
    _, org = await signup(api, "organisation")
    with_duration = (await api.post("/campaigns", headers=auth(org), json=campaign_body(duration_days=14))).json()
    assert with_duration["end_condition"] == "duration"
    no_duration = (
        await api.post("/campaigns", headers=auth(org), json=campaign_body(duration_days=None, expected_views=1000))
    ).json()
    assert no_duration["end_condition"] == "budget"


# --- per-video cap and max submissions --------------------------------------------------------------


async def test_video_cap_stops_a_single_clip_short_of_the_creator_cap(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(
        api, org, expected_views=1_000_000,
        payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0, "video_cap_amount": 2000},
    )
    assert campaign["video_cap"] == 2000
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await earn(api, intel, sid, 12_000)  # would be ₦6,000 uncapped
    await clear_hold(creator["user"]["id"])
    summary = (await api.get("/earnings/summary", headers=auth(creator))).json()
    assert summary["payable"] == 2000  # stopped at the per-video cap


async def test_max_submissions_blocks_a_creator_past_the_limit(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(
        api, org, expected_views=1_000_000,
        payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0, "max_submissions": 1},
    )
    assert campaign["max_submissions"] == 1
    creator = await make_creator(api)
    first = await submit_clip(api, creator, campaign["id"])
    assert first.status_code == 201
    second = await submit_clip(api, creator, campaign["id"], url="https://www.tiktok.com/@creator/video/999999")
    assert second.status_code == 409


# --- full-freeze pause -------------------------------------------------------------------------------


async def test_full_freeze_stops_accrual_on_approved_clips_until_resumed(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org, expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0})
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await earn(api, intel, sid, 6_000)  # ₦3,000 before freezing

    paused = await api.post(f"/campaigns/{campaign['id']}/pause", headers=auth(org), params={"mode": "full"})
    assert paused.status_code == 200 and paused.json()["payouts_frozen"] is True and paused.json()["accepting_entries"] is False

    await earn(api, intel, sid, 12_000)  # more views while frozen: nothing new is booked
    summary = (await api.get("/earnings/summary", headers=auth(creator))).json()
    assert summary["in_hold"] == 3000  # unchanged

    resumed = await api.post(f"/campaigns/{campaign['id']}/resume", headers=auth(org))
    assert resumed.json()["payouts_frozen"] is False

    await earn(api, intel, sid, 12_000)  # same reading as while frozen: now it settles
    summary = (await api.get("/earnings/summary", headers=auth(creator))).json()
    assert summary["in_hold"] == 6000


async def test_acquisition_only_pause_leaves_payouts_running(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org, expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0})
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]

    paused = await api.post(f"/campaigns/{campaign['id']}/pause", headers=auth(org))  # default mode
    assert paused.json()["payouts_frozen"] is False and paused.json()["accepting_entries"] is False

    await earn(api, intel, sid, 6_000)
    summary = (await api.get("/earnings/summary", headers=auth(creator))).json()
    assert summary["in_hold"] == 3000  # still accrues
