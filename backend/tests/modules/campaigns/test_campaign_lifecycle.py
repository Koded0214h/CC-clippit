from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from tests.http_app import api, auth, campaign_body, db_session, fund_campaign, open_campaign, signup  # noqa: F401


async def _draft(api, org, **overrides):
    r = await api.post("/campaigns", headers=auth(org), json=campaign_body(**overrides))
    assert r.status_code == 201, r.text
    return r.json()


# --- the budget identity -----------------------------------------------------------


async def test_pot_buys_views_at_the_rate(api):
    _, org = await signup(api, "organisation")
    c = await _draft(api, org, pot=500000, expected_views=None, payout_rule={"rate_per_1000_views": 500})
    assert c["pot"] == 500000
    assert c["expected_views"] == 1_000_000  # ₦500,000 ÷ ₦500 × 1,000
    assert c["remaining"] == 500000 and c["spent"] == 0


async def test_expected_views_derives_the_pot(api):
    _, org = await signup(api, "organisation")
    c = await _draft(api, org, expected_views=200000, payout_rule={"rate_per_1000_views": 650})
    assert c["pot"] == 130000


async def test_partial_thousands_are_floored_not_rounded_up(api):
    _, org = await signup(api, "organisation")
    c = await _draft(api, org, pot=1000, expected_views=None, payout_rule={"rate_per_1000_views": 300})
    assert c["expected_views"] == 3333  # 3.333 thousand → 3,333, never 3,334


async def test_a_pot_that_buys_nothing_is_refused(api):
    _, org = await signup(api, "organisation")
    r = await api.post("/campaigns", headers=auth(org), json=campaign_body(pot=0.4, expected_views=None, payout_rule={"rate_per_1000_views": 500}))
    assert r.status_code == 422


async def test_a_budget_is_required(api):
    _, org = await signup(api, "organisation")
    body = campaign_body()
    del body["expected_views"]
    assert (await api.post("/campaigns", headers=auth(org), json=body)).status_code == 422


async def test_changing_the_rate_rescales_the_views_the_pot_buys(api):
    _, org = await signup(api, "organisation")
    c = await _draft(api, org, pot=500000, expected_views=None, payout_rule={"rate_per_1000_views": 500})
    r = await api.put(f"/campaigns/{c['id']}/payout-rule", headers=auth(org), json={"rate_per_1000_views": 1000})
    assert r.status_code == 200
    after = (await api.get(f"/campaigns/{c['id']}", headers=auth(org))).json()
    assert after["pot"] == 500000 and after["expected_views"] == 500000


# --- identity: slugs ----------------------------------------------------------------


async def test_slug_is_generated_unique_and_routable(api):
    _, org = await signup(api, "organisation")
    a = await _draft(api, org, title="No long thing")
    b = await _draft(api, org, title="No long thing")
    assert a["slug"] == "no-long-thing" and b["slug"] != a["slug"] and b["slug"].startswith("no-long-thing-")
    by_slug = await api.get(f"/campaigns/{a['slug']}", headers=auth(org))
    assert by_slug.status_code == 200 and by_slug.json()["id"] == a["id"]


async def test_draft_is_invisible_to_outsiders_by_slug_and_id(api):
    _, org = await signup(api, "organisation")
    _, other = await signup(api, "organisation")
    _, creator = await signup(api, "creator")
    c = await _draft(api, org, title="Secret draft")
    for viewer in (other, creator):
        for ref in (c["id"], c["slug"]):
            assert (await api.get(f"/campaigns/{ref}", headers=auth(viewer))).status_code == 404


async def test_only_organisations_create_campaigns_and_only_verified_ones(api):
    _, creator = await signup(api, "creator")
    assert (await api.post("/campaigns", headers=auth(creator), json=campaign_body())).status_code == 403
    _, unverified = await signup(api, "organisation", verify=False)
    r = await api.post("/campaigns", headers=auth(unverified), json=campaign_body())
    assert r.status_code == 403 and r.json()["detail"]["code"] == "email_not_verified"


# --- the brief -----------------------------------------------------------------------


async def test_rules_are_replaced_as_a_list_and_keep_their_order(api):
    _, org = await signup(api, "organisation")
    c = await _draft(api, org, rules=[{"kind": "must", "text": "Show the noodles clearly"}])
    r = await api.put(
        f"/campaigns/{c['id']}/rules",
        headers=auth(org),
        json={"rules": [
            {"kind": "must", "text": "Say or display: No long thing."},
            {"kind": "avoid", "text": "Do not make health claims."},
            {"kind": "must", "text": "Tag the brand in the caption."},
        ]},
    )
    assert r.status_code == 200
    assert [x["text"] for x in r.json()] == ["Say or display: No long thing.", "Do not make health claims.", "Tag the brand in the caption."]
    assert [x["position"] for x in r.json()] == [0, 1, 2]
    detail = (await api.get(f"/campaigns/{c['id']}", headers=auth(org))).json()
    assert [x["kind"] for x in detail["rules"]] == ["must", "avoid", "must"]


async def test_short_rule_is_rejected(api):
    _, org = await signup(api, "organisation")
    c = await _draft(api, org)
    r = await api.put(f"/campaigns/{c['id']}/rules", headers=auth(org), json={"rules": [{"kind": "must", "text": "Hi"}]})
    assert r.status_code == 422


# --- funding ---------------------------------------------------------------------------


async def test_funding_order_quotes_pot_fee_and_total(api):
    _, org = await signup(api, "organisation")
    c = await _draft(api, org, pot=500000, expected_views=None, payout_rule={"rate_per_1000_views": 500})
    r = await api.post(f"/campaigns/{c['id']}/funding", headers=auth(org), json={"method": "bank"})
    assert r.status_code == 201
    order = r.json()
    assert order["pot"] == 500000 and order["fee"] == 75000 and order["total"] == 575000  # 15% fee
    assert order["status"] == "awaiting_payment" and order["sandbox"] is True
    assert order["reference"].startswith("CLP-")
    assert order["collection"]["account_number"] and len(order["collection"]["account_number"]) == 10
    assert order["campaign_status"] == "pending_funding"


async def test_starting_funding_twice_returns_the_same_order(api):
    _, org = await signup(api, "organisation")
    c = await _draft(api, org)
    first = (await api.post(f"/campaigns/{c['id']}/funding", headers=auth(org), json={"method": "bank"})).json()
    second = (await api.post(f"/campaigns/{c['id']}/funding", headers=auth(org), json={"method": "bank"})).json()
    assert first["id"] == second["id"] and first["reference"] == second["reference"]


async def test_switching_method_replaces_an_unpaid_order(api):
    _, org = await signup(api, "organisation")
    c = await _draft(api, org)
    bank = (await api.post(f"/campaigns/{c['id']}/funding", headers=auth(org), json={"method": "bank"})).json()
    card = (await api.post(f"/campaigns/{c['id']}/funding", headers=auth(org), json={"method": "card"})).json()
    assert card["id"] != bank["id"] and card["collection"] is None


async def test_terms_lock_when_funding_starts_and_unlock_on_cancel(api):
    _, org = await signup(api, "organisation")
    c = await _draft(api, org, title="Lock me")
    await api.post(f"/campaigns/{c['id']}/funding", headers=auth(org), json={"method": "bank"})

    assert (await api.patch(f"/campaigns/{c['id']}", headers=auth(org), json={"title": "Changed"})).status_code == 409
    assert (await api.put(f"/campaigns/{c['id']}/payout-rule", headers=auth(org), json={"rate_per_1000_views": 9})).status_code == 409
    assert (await api.put(f"/campaigns/{c['id']}/rules", headers=auth(org), json={"rules": []})).status_code == 409

    cancelled = await api.delete(f"/campaigns/{c['id']}/funding", headers=auth(org))
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert (await api.get(f"/campaigns/{c['id']}", headers=auth(org))).json()["status"] == "draft"
    assert (await api.patch(f"/campaigns/{c['id']}", headers=auth(org), json={"title": "Changed"})).status_code == 200


async def test_confirming_opens_the_campaign_and_starts_the_clock(api):
    _, org = await signup(api, "organisation")
    c = await _draft(api, org, duration_days=14)
    await api.post(f"/campaigns/{c['id']}/funding", headers=auth(org), json={"method": "bank"})
    r = await api.post(f"/campaigns/{c['id']}/funding/confirm", headers=auth(org))
    assert r.status_code == 200 and r.json()["status"] == "confirmed" and r.json()["campaign_status"] == "active"

    live = (await api.get(f"/campaigns/{c['id']}", headers=auth(org))).json()
    assert live["phase"] == "Live" and live["accepting_entries"] is True
    ends = datetime.fromisoformat(live["ends_at"])
    assert timedelta(days=13, hours=23) < ends - datetime.now(timezone.utc) < timedelta(days=14, minutes=1)
    assert live["time_left"]["days"] >= 13 and live["time_left"]["ended"] is False


async def test_confirming_twice_is_harmless(api):
    _, org = await signup(api, "organisation")
    c = await _draft(api, org)
    await api.post(f"/campaigns/{c['id']}/funding", headers=auth(org), json={"method": "bank"})
    a = await api.post(f"/campaigns/{c['id']}/funding/confirm", headers=auth(org))
    b = await api.post(f"/campaigns/{c['id']}/funding/confirm", headers=auth(org))
    assert a.status_code == b.status_code == 200 and a.json()["confirmed_at"] == b.json()["confirmed_at"]


async def test_cannot_fund_without_a_rate_or_a_confirmed_pot_open_by_activate(api):
    _, org = await signup(api, "organisation")
    c = await _draft(api, org)
    assert (await api.post(f"/campaigns/{c['id']}/activate", headers=auth(org))).status_code == 409
    await api.post(f"/campaigns/{c['id']}/funding", headers=auth(org), json={"method": "bank"})
    assert (await api.post(f"/campaigns/{c['id']}/activate", headers=auth(org))).status_code == 409  # ordered, not paid


async def test_only_the_owner_can_fund(api):
    _, org = await signup(api, "organisation")
    _, other = await signup(api, "organisation")
    c = await _draft(api, org)
    assert (await api.post(f"/campaigns/{c['id']}/funding", headers=auth(other), json={"method": "bank"})).status_code == 403


async def test_funding_a_closed_campaign_is_refused(api):
    _, org = await signup(api, "organisation")
    c = await open_campaign(api, org)
    await api.post(f"/campaigns/{c['id']}/close", headers=auth(org))
    assert (await api.post(f"/campaigns/{c['id']}/funding", headers=auth(org), json={"method": "bank"})).status_code == 409


# --- lifecycle -----------------------------------------------------------------------------


async def test_pause_resume_and_close(api):
    _, org = await signup(api, "organisation")
    c = await open_campaign(api, org)
    p = await api.post(f"/campaigns/{c['id']}/pause", headers=auth(org))
    assert p.json()["accepting_entries"] is False and p.json()["status"] == "active"
    r = await api.post(f"/campaigns/{c['id']}/resume", headers=auth(org))
    assert r.json()["accepting_entries"] is True
    closed = await api.post(f"/campaigns/{c['id']}/close", headers=auth(org))
    assert closed.json()["status"] == "closed" and closed.json()["phase"] == "Completed"
    assert (await api.post(f"/campaigns/{c['id']}/close", headers=auth(org))).status_code == 409
    assert (await api.post(f"/campaigns/{c['id']}/pause", headers=auth(org))).status_code == 409


async def test_a_draft_cannot_be_paused(api):
    _, org = await signup(api, "organisation")
    c = await _draft(api, org)
    assert (await api.post(f"/campaigns/{c['id']}/pause", headers=auth(org))).status_code == 409


async def test_expired_campaigns_are_closed_by_the_sweep(api):
    from modules.campaigns import models
    from modules.campaigns.service import close_due_campaigns

    _, org = await signup(api, "organisation")
    fresh = await open_campaign(api, org, title="Still running")
    old = await open_campaign(api, org, title="Ran out of time")
    async with db_session() as db:
        row = await db.scalar(select(models.Campaign).where(models.Campaign.id == old["id"]))
        row.ends_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db.commit()
        assert await close_due_campaigns(db) == 1
        assert await close_due_campaigns(db) == 0  # idempotent

    assert (await api.get(f"/campaigns/{old['id']}", headers=auth(org))).json()["status"] == "closed"
    assert (await api.get(f"/campaigns/{fresh['id']}", headers=auth(org))).json()["status"] == "active"


# --- browsing --------------------------------------------------------------------------------


async def test_creators_only_browse_live_campaigns_with_a_feed_status(api):
    _, org = await signup(api, "organisation")
    _, creator = await signup(api, "creator")
    await _draft(api, org, title="Hidden draft")
    live = await open_campaign(api, org, title="Visible one", category="Comedy")
    listed = (await api.get("/campaigns", headers=auth(creator))).json()
    assert [c["title"] for c in listed] == ["Visible one"]
    card = listed[0]
    assert card["feed_status"] == "Open" and card["joined"] is False
    assert card["metrics"] is None  # a creator never sees the brand's numbers
    assert card["brand"]["name"] == "Test organisation"


async def test_search_category_platform_and_brand_filters(api):
    _, org = await signup(api, "organisation")
    _, creator = await signup(api, "creator")
    await api.put("/organisations/me/profile", headers=auth(org), json={"name": "Indomie"})
    await open_campaign(api, org, title="No long thing", category="Comedy", platforms=["tiktok", "instagram"])
    await open_campaign(api, org, title="Face card", category="Beauty", platforms=["instagram", "youtube"])

    def titles(resp):
        return sorted(c["title"] for c in resp.json())

    assert titles(await api.get("/campaigns?q=long", headers=auth(creator))) == ["No long thing"]
    assert titles(await api.get("/campaigns?q=indomie", headers=auth(creator))) == ["Face card", "No long thing"]  # brand name
    assert titles(await api.get("/campaigns?category=beauty", headers=auth(creator))) == ["Face card"]
    assert titles(await api.get("/campaigns?platform=youtube", headers=auth(creator))) == ["Face card"]
    assert titles(await api.get("/campaigns?platform=tiktok", headers=auth(creator))) == ["No long thing"]


async def test_for_you_uses_the_creators_lanes(api):
    _, org = await signup(api, "organisation")
    _, creator = await signup(api, "creator")
    await open_campaign(api, org, title="Funny one", category="Comedy")
    await open_campaign(api, org, title="Gamey one", category="Gaming")
    await api.put("/creators/me/onboarding", headers=auth(creator), json={"display_name": "Tobi", "interests": ["Comedy"]})
    out = (await api.get("/campaigns?feed=for_you", headers=auth(creator))).json()
    assert [c["title"] for c in out] == ["Funny one"]


async def test_closing_soon_feed_and_time_left(api):
    _, org = await signup(api, "organisation")
    _, creator = await signup(api, "creator")
    await open_campaign(api, org, title="Ends tomorrow", duration_days=1)
    await open_campaign(api, org, title="Ends later", duration_days=30)
    soon = (await api.get("/campaigns?feed=closing_soon", headers=auth(creator))).json()
    assert [c["title"] for c in soon] == ["Ends tomorrow"]
    assert soon[0]["feed_status"] == "Closing soon"


async def test_organisation_list_shows_every_status_with_metrics(api):
    _, org = await signup(api, "organisation")
    await _draft(api, org, title="A draft")
    await open_campaign(api, org, title="A live one")
    out = (await api.get("/campaigns", headers=auth(org))).json()
    assert {c["phase"] for c in out} == {"Draft", "Live"}
    assert all(c["metrics"] is not None and c["metrics"]["verified_views"] == 0 for c in out)
    only_live = (await api.get("/campaigns?status_filter=active", headers=auth(org))).json()
    assert [c["title"] for c in only_live] == ["A live one"]


# --- brand dashboards --------------------------------------------------------------------------


async def test_stats_are_owner_only(api):
    _, org = await signup(api, "organisation")
    _, other = await signup(api, "organisation")
    c = await open_campaign(api, org, pot=1000, expected_views=None, payout_rule={"rate_per_1000_views": 100})
    stats = await api.get(f"/campaigns/{c['slug']}/stats", headers=auth(org))
    assert stats.status_code == 200
    s = stats.json()
    assert s["phase"] == "Live" and s["pot"] == 1000 and s["remaining"] == 1000 and s["percent_remaining"] == 100
    assert s["submissions"] == 0 and s["accepting_entries"] is True
    assert (await api.get(f"/campaigns/{c['id']}/stats", headers=auth(other))).status_code == 403


async def test_overview_summarises_the_brand(api):
    _, org = await signup(api, "organisation")
    empty = (await api.get("/brand/overview", headers=auth(org))).json()
    assert empty["live_campaigns"] == 0 and empty["featured"] is None and empty["unmatched_spend"] == 0

    await _draft(api, org, title="Later")
    await open_campaign(api, org, title="Now", pot=250000, expected_views=None, payout_rule={"rate_per_1000_views": 500})
    o = (await api.get("/brand/overview", headers=auth(org))).json()
    assert o["live_campaigns"] == 1 and o["draft_campaigns"] == 1 and o["completed_campaigns"] == 0
    assert o["total_pot"] == 250000 and o["total_spent"] == 0 and o["pending_reviews"] == 0
    assert o["featured"]["title"] == "Now"


async def test_overview_is_organisation_only(api):
    _, creator = await signup(api, "creator")
    assert (await api.get("/brand/overview", headers=auth(creator))).status_code == 403


async def test_report_is_csv_and_defangs_formulas(api):
    _, org = await signup(api, "organisation")
    c = await open_campaign(api, org)
    r = await api.get(f"/campaigns/{c['id']}/report", headers=auth(org))
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert r.text.splitlines()[0].startswith("submission_id,creator,handle")

    from modules.campaigns.router import _csv_safe

    assert _csv_safe("=HYPERLINK(\"http://evil\")") == "'=HYPERLINK(\"http://evil\")"
    assert _csv_safe("+1") == "'+1" and _csv_safe("@x") == "'@x" and _csv_safe("Kemi") == "Kemi"
