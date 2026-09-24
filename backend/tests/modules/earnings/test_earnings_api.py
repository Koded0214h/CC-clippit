from decimal import Decimal

from tests.http_app import (  # noqa: F401
    api, auth, clear_hold, earn, intel, make_creator, open_campaign, signup, submit_clip,
)


async def _clip(api, intel, org, creator, campaign, views, title="A clip"):
    sid = (await submit_clip(api, creator, campaign["id"], title=title)).json()["id"]
    await earn(api, intel, sid, views)
    return sid


async def _campaign(api, org, **kw):
    kw.setdefault("payout_rule", {"rate_per_1000_views": 500, "min_views_threshold": 1000})
    kw.setdefault("title", "No long thing")
    if "pot" not in kw:
        kw.setdefault("expected_views", 1_000_000)
    return await open_campaign(api, org, **kw)


async def test_summary_of_a_creator_with_nothing_is_zero_not_an_error(api, intel):
    creator = await make_creator(api)
    s = (await api.get("/earnings/summary", headers=auth(creator))).json()
    assert s["payable"] == 0 and s["in_hold"] == 0 and s["paid_all_time"] == 0 and s["lifetime_views"] == 0
    assert s["hold_days"] == 5 and s["min_withdrawal"] == 5000 and s["next_clears_at"] is None


async def test_new_earnings_sit_in_the_hold_then_become_payable(api, intel):
    _, org = await signup(api, "organisation")
    creator = await make_creator(api)
    campaign = await _campaign(api, org)
    await _clip(api, intel, org, creator, campaign, 12_400)  # 12 thousand × ₦500 = ₦6,000

    s = (await api.get("/earnings/summary", headers=auth(creator))).json()
    assert s["in_hold"] == 6000 and s["payable"] == 0 and s["total_accrued"] == 6000
    assert s["lifetime_views"] == 12_400 and s["added_this_week"] == 6000 and s["active_clips"] == 1
    assert s["next_clears_at"] and s["last_earned_at"]

    await clear_hold(creator["user"]["id"])
    s = (await api.get("/earnings/summary", headers=auth(creator))).json()
    assert s["payable"] == 6000 and s["in_hold"] == 0 and s["next_clears_at"] is None


async def test_history_lists_each_accrual_with_its_state(api, intel):
    _, org = await signup(api, "organisation")
    creator = await make_creator(api)
    campaign = await _campaign(api, org)
    sid = await _clip(api, intel, org, creator, campaign, 3000, title="Hunger interrupted the group chat")
    await clear_hold(creator["user"]["id"])
    await earn(api, intel, sid, 5000)  # a second, fresh entry still in hold

    h = (await api.get("/earnings/history", headers=auth(creator))).json()
    assert h["total"] == 2
    newest, oldest = h["items"]
    assert newest["state"] == "Accrued" and newest["amount"] == 1000 and newest["billable_views"] == 2000
    assert oldest["state"] == "Payable" and oldest["amount"] == 1500 and oldest["billable_views"] == 3000
    assert oldest["clip"] == "Hunger interrupted the group chat" and oldest["campaign_title"] == "No long thing"
    assert oldest["brand"] == "Test organisation"


async def test_history_paginates(api, intel):
    _, org = await signup(api, "organisation")
    creator = await make_creator(api)
    campaign = await _campaign(api, org)
    sid = await _clip(api, intel, org, creator, campaign, 1000)
    for views in (2000, 3000, 4000):
        await earn(api, intel, sid, views)
    page = (await api.get("/earnings/history?limit=2&offset=0", headers=auth(creator))).json()
    assert page["total"] == 4 and len(page["items"]) == 2
    assert len((await api.get("/earnings/history?limit=2&offset=2", headers=auth(creator))).json()["items"]) == 2


async def test_earnings_are_creator_only_and_private(api, intel):
    _, org = await signup(api, "organisation")
    assert (await api.get("/earnings/summary", headers=auth(org))).status_code == 403
    assert (await api.get("/earnings/history", headers=auth(org))).status_code == 403
    a = await make_creator(api)
    b = await make_creator(api)
    campaign = await _campaign(api, org)
    await _clip(api, intel, org, a, campaign, 5000)
    assert (await api.get("/earnings/summary", headers=auth(b))).json()["total_accrued"] == 0
    assert (await api.get("/earnings/history", headers=auth(b))).json()["items"] == []


async def test_the_brand_sees_spend_verified_views_and_the_pot_drawn_down(api, intel):
    _, org = await signup(api, "organisation")
    creator = await make_creator(api)
    campaign = await _campaign(api, org, pot=500000, expected_views=None)
    await _clip(api, intel, org, creator, campaign, 12_400)

    c = (await api.get(f"/campaigns/{campaign['id']}", headers=auth(org))).json()
    assert c["spent"] == 6000 and c["remaining"] == 494000
    assert c["metrics"]["verified_views"] == 12_400 and c["metrics"]["approved"] == 1 and c["metrics"]["earned"] == 6000

    stats = (await api.get(f"/campaigns/{campaign['id']}/stats", headers=auth(org))).json()
    assert stats["spent"] == 6000 and stats["views_last_24h"] == 12_400 and stats["last_reading_at"]
    rows = (await api.get(f"/campaigns/{campaign['id']}/submissions", headers=auth(org))).json()
    assert rows[0]["verified_views"] == 12_400 and rows[0]["earned"] == 6000 and rows[0]["state"] == "Earning"

    o = (await api.get("/brand/overview", headers=auth(org))).json()
    assert o["total_spent"] == 6000 and o["views_last_24h"] == 12_400 and o["earnings_last_24h"] == 6000


async def test_the_submission_earnings_card(api, intel):
    _, org = await signup(api, "organisation")
    creator = await make_creator(api)
    campaign = await _campaign(api, org)
    sid = await _clip(api, intel, org, creator, campaign, 12_400)
    e = (await api.get(f"/submissions/{sid}/earnings", headers=auth(creator))).json()
    assert e["verified_views"] == 12_400 and e["accrued"] == 6000 and e["payable_now"] == 0 and e["next_payable_at"]
    await clear_hold(creator["user"]["id"])
    e = (await api.get(f"/submissions/{sid}/earnings", headers=auth(creator))).json()
    assert e["payable_now"] == 6000 and e["next_payable_at"] is None


# --- leaderboard ---------------------------------------------------------------------------------------------


async def test_leaderboard_ranks_creators_by_verified_views(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await _campaign(api, org)
    zara = await make_creator(api, handle="@zaramakes")
    await api.put("/creators/me/profile", headers=auth(zara), json={"display_name": "Zara Makes"})
    tobi = await make_creator(api, handle="@tobioncam")
    await api.put("/creators/me/profile", headers=auth(tobi), json={"display_name": "Tobi On Cam"})
    lurker = await make_creator(api)
    await _clip(api, intel, org, zara, campaign, 184_200)
    await _clip(api, intel, org, tobi, campaign, 156_800)

    for period in ("week", "all"):
        lb = (await api.get(f"/leaderboard?period={period}", headers=auth(tobi))).json()
        assert [r["name"] for r in lb["items"]] == ["Zara Makes", "Tobi On Cam"], period
        assert lb["items"][0]["rank"] == 1 and lb["items"][0]["handle"] == "@zaramakes"
        assert lb["items"][0]["views"] > lb["items"][1]["views"] and lb["items"][0]["earned"] > 0
        assert lb["me"]["rank"] == 2 and lb["me"]["is_me"] is True
        assert [r["is_me"] for r in lb["items"]] == [False, True]
    assert (await api.get("/leaderboard", headers=auth(lurker))).json()["me"] is None  # earning nothing yet


async def test_leaderboard_reports_the_callers_rank_even_below_the_cut(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await _campaign(api, org)
    creators = [await make_creator(api) for _ in range(3)]
    for creator, views in zip(creators, (9000, 5000, 2000)):
        await _clip(api, intel, org, creator, campaign, views)
    lb = (await api.get("/leaderboard?limit=1", headers=auth(creators[2]))).json()
    assert len(lb["items"]) == 1 and lb["me"]["rank"] == 3


async def test_leaderboard_can_be_limited_to_one_campaign(api, intel):
    _, org = await signup(api, "organisation")
    one = await _campaign(api, org, title="One")
    two = await _campaign(api, org, title="Two")
    a = await make_creator(api)
    b = await make_creator(api)
    await _clip(api, intel, org, a, one, 9000)
    await _clip(api, intel, org, b, two, 4000)
    lb = (await api.get(f"/leaderboard?campaign_id={two['id']}&period=all", headers=auth(a))).json()
    assert len(lb["items"]) == 1 and lb["items"][0]["views"] == 4000 and lb["me"] is None


async def test_leaderboard_country_scope_narrows_to_the_viewers_own_country(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await _campaign(api, org)
    ng = await make_creator(api)
    await api.put("/creators/me/profile", headers=auth(ng), json={"country": "ng"})
    gh = await make_creator(api)
    await api.put("/creators/me/profile", headers=auth(gh), json={"country": "GH"})
    no_country = await make_creator(api)
    await _clip(api, intel, org, ng, campaign, 9000)
    await _clip(api, intel, org, gh, campaign, 5000)
    await _clip(api, intel, org, no_country, campaign, 20_000)

    lb = (await api.get("/leaderboard?scope=country&period=all", headers=auth(ng))).json()
    assert lb["scope"] == "country" and [r["views"] for r in lb["items"]] == [9000]  # lowercase normalized to NG, GH excluded

    empty = (await api.get("/leaderboard?scope=country&period=all", headers=auth(no_country))).json()
    assert empty["items"] == [] and empty["me"] is None  # no country set yet: an empty board, not an error

    still_global = (await api.get("/leaderboard?period=all", headers=auth(ng))).json()
    assert still_global["scope"] == "global" and len(still_global["items"]) == 3
