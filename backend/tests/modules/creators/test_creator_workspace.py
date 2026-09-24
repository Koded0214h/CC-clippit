from tests.http_app import (  # noqa: F401
    api, approve_clip, auth, clear_hold, earn, intel, make_creator, open_campaign, signup, submit_clip,
)

RULES = [{"kind": "must", "text": "Show the product clearly."}]


async def test_my_clips_lists_each_clip_with_status_views_and_earnings(api, intel):
    _, org = await signup(api, "organisation")
    await api.put("/organisations/me/profile", headers=auth(org), json={"name": "Indomie"})
    campaign = await open_campaign(api, org, title="No long thing", expected_views=1_000_000,
                                   payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 1000})
    rules_campaign = await open_campaign(api, org, title="Main character", rules=RULES, expected_views=1_000_000,
                                         payout_rule={"rate_per_1000_views": 400, "min_views_threshold": 1000})
    creator = await make_creator(api)
    approved = (await submit_clip(api, creator, campaign["id"], title="Hunger interrupted the group chat")).json()["id"]
    await earn(api, intel, approved, 12_400)
    checking = (await submit_clip(api, creator, rules_campaign["id"], title="The main-character entrance")).json()["id"]
    rejected = (await submit_clip(api, creator, rules_campaign["id"], title="Who paid for the ride?")).json()["id"]
    await api.post(f"/brand/reviews/{rejected}/request-correction", headers=auth(org), json={"reason": "Product hidden."})

    out = (await api.get("/creators/me/clips", headers=auth(creator))).json()
    by_title = {c["title"]: c for c in out["items"]}
    a = by_title["Hunger interrupted the group chat"]
    assert (a["status"], a["label"], a["verified_views"], a["earned"]) == ("approved", "Approved", 12_400, 6000)
    assert a["campaign_title"] == "No long thing" and a["brand"] == "Indomie"
    assert a["link"] == f"/dashboard/submissions/approved?id={approved}"
    c = by_title["The main-character entrance"]
    assert (c["status"], c["label"], c["earned"]) == ("checking", "Checking", 0) and c["link"].startswith("/dashboard/submissions/processing")
    r = by_title["Who paid for the ride?"]
    assert (r["status"], r["label"]) == ("needs_attention", "Needs attention") and r["link"].startswith("/dashboard/submissions/rejected")

    assert out["active_clips"] == 2  # approved + checking; the rejected one isn't active
    assert out["verified_views"] == 12_400 and out["total_earned"] == 6000


async def test_my_clips_is_private_and_creator_only(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org)
    a = await make_creator(api)
    b = await make_creator(api)
    await submit_clip(api, a, campaign["id"])
    assert (await api.get("/creators/me/clips", headers=auth(b))).json()["items"] == []
    assert (await api.get("/creators/me/clips", headers=auth(org))).status_code == 403


async def test_a_withdrawn_clip_is_labelled_and_not_active(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org)
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await api.post(f"/submissions/{sid}/withdraw", headers=auth(creator))
    out = (await api.get("/creators/me/clips", headers=auth(creator))).json()
    assert out["items"][0]["status"] == "withdrawn" and out["active_clips"] == 0


async def test_connected_accounts_list_every_platform_and_what_can_be_connected(api, intel):
    creator = await make_creator(api, platform="tiktok", handle="@tobioncam")
    accounts = {a["platform"]: a for a in (await api.get("/creators/me/accounts", headers=auth(creator))).json()}
    assert set(accounts) == {"tiktok", "instagram", "facebook", "threads", "x", "youtube"}
    t = accounts["tiktok"]
    assert t["connected"] is True and t["handle"] == "@tobioncam" and t["connectable"] is True and t["connected_at"]
    assert accounts["instagram"]["connected"] is False and accounts["instagram"]["connectable"] is True
    # YouTube is connectable once the OAuth provider is registered.
    assert accounts["youtube"]["connectable"] is True and accounts["youtube"]["connected"] is False


async def test_last_checked_is_when_clippit_last_read_a_post_on_that_platform(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org, expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0})
    creator = await make_creator(api)
    before = {a["platform"]: a for a in (await api.get("/creators/me/accounts", headers=auth(creator))).json()}
    assert before["tiktok"]["last_checked_at"] is None
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await earn(api, intel, sid, 3000)
    after = {a["platform"]: a for a in (await api.get("/creators/me/accounts", headers=auth(creator))).json()}
    assert after["tiktok"]["last_checked_at"] is not None and after["instagram"]["last_checked_at"] is None


async def test_disconnecting_an_account_flows_through(api, intel):
    creator = await make_creator(api)
    assert (await api.delete("/social/tiktok", headers=auth(creator))).status_code == 204
    accounts = {a["platform"]: a for a in (await api.get("/creators/me/accounts", headers=auth(creator))).json()}
    assert accounts["tiktok"]["connected"] is False


async def test_the_dashboard_home_in_one_call(api, intel):
    _, org = await signup(api, "organisation")
    await open_campaign(api, org, title="Ends soon", category="Comedy", duration_days=2)
    await open_campaign(api, org, title="Ends later", category="Comedy", duration_days=30)
    await open_campaign(api, org, title="Different lane", category="Gaming", duration_days=30)
    creator = await make_creator(api)
    await api.put("/creators/me/onboarding", headers=auth(creator), json={"display_name": "Tobi", "interests": ["Comedy"]})

    home = (await api.get("/creators/me/overview", headers=auth(creator))).json()
    assert home["closing_soon"]["title"] == "Ends soon" and home["closing_soon"]["feed_status"] == "Closing soon"
    assert home["new_matches"] == 2  # the two Comedy campaigns, not the Gaming one
    assert home["earnings"]["payable"] == 0 and home["earnings"]["hold_days"] == 5


async def test_the_dashboard_home_with_nothing_live_is_empty_not_an_error(api, intel):
    creator = await make_creator(api)
    home = (await api.get("/creators/me/overview", headers=auth(creator))).json()
    assert home["closing_soon"] is None and home["new_matches"] == 0


async def test_joining_a_campaign_removes_it_from_new_matches(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org, title="Comedy one", category="Comedy")
    creator = await make_creator(api)
    await api.put("/creators/me/onboarding", headers=auth(creator), json={"display_name": "Tobi", "interests": ["Comedy"]})
    assert (await api.get("/creators/me/overview", headers=auth(creator))).json()["new_matches"] == 1
    await submit_clip(api, creator, campaign["id"])
    assert (await api.get("/creators/me/overview", headers=auth(creator))).json()["new_matches"] == 0
    feed = (await api.get("/campaigns?feed=joined", headers=auth(creator))).json()
    assert [c["title"] for c in feed] == ["Comedy one"] and feed[0]["feed_status"] == "Joined" and feed[0]["joined"] is True
    assert (await api.get("/campaigns?feed=open", headers=auth(creator))).json() == []
