"""The campaign studio's resumable draft lifecycle
(production-api-inventory.md §H)."""

import pytest

from tests.http_app import api, auth, fund_campaign, signup


async def _draft(api, org):
    return (await api.post("/campaign-drafts", headers=auth(org))).json()


async def test_a_fresh_draft_lists_every_missing_screen(api):
    _, org = await signup(api, "organisation")
    d = await _draft(api, org)
    assert d["status"] == "not_started" and d["revision"] == 0
    assert set(d["blockers"]) == {"title", "description", "platforms", "payout_rule", "budget"}


async def test_autosave_accumulates_across_screens_and_narrows_blockers(api):
    _, org = await signup(api, "organisation")
    d = await _draft(api, org)

    step1 = await api.patch(
        f"/campaign-drafts/{d['id']}", headers=auth(org),
        json={"revision": 0, "step": "details", "title": "Sprint Launch", "description": "A launch push"},
    )
    assert step1.status_code == 200
    body = step1.json()
    assert body["status"] == "in_progress" and body["revision"] == 1
    assert "title" not in body["blockers"] and "platforms" in body["blockers"]

    step2 = await api.patch(
        f"/campaign-drafts/{d['id']}", headers=auth(org),
        json={"revision": 1, "step": "platforms", "platforms": ["tiktok"]},
    )
    assert "platforms" not in step2.json()["blockers"]

    step3 = await api.patch(
        f"/campaign-drafts/{d['id']}", headers=auth(org),
        json={"revision": 2, "step": "budget", "payout_rule": {"rate_per_1000_views": 500}, "pot": 50000},
    )
    assert step3.json()["blockers"] == {}


async def test_a_stale_revision_is_refused(api):
    _, org = await signup(api, "organisation")
    d = await _draft(api, org)
    await api.patch(f"/campaign-drafts/{d['id']}", headers=auth(org), json={"revision": 0, "title": "First"})
    stale = await api.patch(f"/campaign-drafts/{d['id']}", headers=auth(org), json={"revision": 0, "title": "Second"})
    assert stale.status_code == 409


async def test_conversion_setup_can_autosave_before_the_store_url_is_complete(api):
    _, org = await signup(api, "organisation")
    d = await _draft(api, org)

    partial = await api.patch(
        f"/campaign-drafts/{d['id']}",
        headers=auth(org),
        json={
            "revision": 0,
            "step": "metrics",
            "performance_metrics": [
                {"metric_type": "view", "rate_amount": 500, "unit_size": 1000},
                {"metric_type": "purchase", "rate_amount": 1000, "unit_size": 1},
            ],
            "conversion_setup": {
                "destination_type": "website",
                "destination_url": "https://",
                "attribution_window_days": 30,
                "attribution_model": "last_touch",
            },
        },
    )

    assert partial.status_code == 200, partial.text
    assert partial.json()["answers"]["conversion_setup"]["destination_url"] == "https://"
    # The saved draft is allowed to be partial, but campaign creation is not.
    finalized = await api.post(f"/campaign-drafts/{d['id']}/finalize", headers=auth(org))
    assert finalized.status_code == 422


async def test_finalize_needs_every_blocker_cleared_and_then_creates_a_real_campaign(api):
    _, org = await signup(api, "organisation")
    d = await _draft(api, org)

    incomplete = await api.post(f"/campaign-drafts/{d['id']}/finalize", headers=auth(org))
    assert incomplete.status_code == 422

    await api.patch(
        f"/campaign-drafts/{d['id']}", headers=auth(org),
        json={
            "revision": 0, "title": "Sprint Launch", "description": "A launch push",
            "platforms": ["tiktok"], "payout_rule": {"rate_per_1000_views": 500}, "pot": 50000,
        },
    )
    done = await api.post(f"/campaign-drafts/{d['id']}/finalize", headers=auth(org))
    assert done.status_code == 200
    body = done.json()
    assert body["campaign_slug"] and body["next_route"].endswith("/fund")

    campaign = await api.get(f"/campaigns/{body['campaign_id']}", headers=auth(org))
    assert campaign.status_code == 200 and campaign.json()["title"] == "Sprint Launch" and campaign.json()["status"] == "draft"


async def test_a_finalized_and_funded_draft_appears_in_the_creator_feed(api):
    _, org = await signup(api, "organisation")
    _, creator = await signup(api, "creator")
    draft = await _draft(api, org)

    saved = await api.patch(
        f"/campaign-drafts/{draft['id']}",
        headers=auth(org),
        json={
            "revision": 0,
            "title": "Creator Feed Launch",
            "description": "A complete campaign created through the resumable studio.",
            "category": "Comedy",
            "platforms": ["tiktok"],
            "payout_rule": {"rate_per_1000_views": 500},
            "pot": 50000,
        },
    )
    assert saved.status_code == 200, saved.text

    finalized = await api.post(f"/campaign-drafts/{draft['id']}/finalize", headers=auth(org))
    assert finalized.status_code == 200, finalized.text
    campaign = finalized.json()

    before_funding = (await api.get("/campaigns", headers=auth(creator))).json()
    assert campaign["campaign_slug"] not in {row["slug"] for row in before_funding}

    funded = await fund_campaign(api, org, campaign["campaign_id"])
    assert funded["campaign_status"] == "active"

    creator_feed = await api.get("/campaigns", headers=auth(creator), params={"feed": "all"})
    assert creator_feed.status_code == 200, creator_feed.text
    visible = {row["slug"]: row for row in creator_feed.json()}
    assert campaign["campaign_slug"] in visible
    assert visible[campaign["campaign_slug"]]["status"] == "active"
    assert visible[campaign["campaign_slug"]]["feed_status"] == "Open"


async def test_finalize_is_idempotent(api):
    _, org = await signup(api, "organisation")
    d = await _draft(api, org)
    await api.patch(
        f"/campaign-drafts/{d['id']}", headers=auth(org),
        json={
            "revision": 0, "title": "Sprint Launch", "description": "A launch push",
            "platforms": ["tiktok"], "payout_rule": {"rate_per_1000_views": 500}, "pot": 50000,
        },
    )
    first = await api.post(f"/campaign-drafts/{d['id']}/finalize", headers=auth(org))
    second = await api.post(f"/campaign-drafts/{d['id']}/finalize", headers=auth(org))
    assert first.json() == second.json()


async def test_a_finalized_draft_cannot_be_patched_or_deleted(api):
    _, org = await signup(api, "organisation")
    d = await _draft(api, org)
    await api.patch(
        f"/campaign-drafts/{d['id']}", headers=auth(org),
        json={
            "revision": 0, "title": "Sprint Launch", "description": "A launch push",
            "platforms": ["tiktok"], "payout_rule": {"rate_per_1000_views": 500}, "pot": 50000,
        },
    )
    await api.post(f"/campaign-drafts/{d['id']}/finalize", headers=auth(org))

    blocked_patch = await api.patch(f"/campaign-drafts/{d['id']}", headers=auth(org), json={"revision": 1, "title": "x"})
    assert blocked_patch.status_code == 409
    blocked_delete = await api.delete(f"/campaign-drafts/{d['id']}", headers=auth(org))
    assert blocked_delete.status_code == 409


async def test_delete_removes_an_incomplete_draft(api):
    _, org = await signup(api, "organisation")
    d = await _draft(api, org)
    r = await api.delete(f"/campaign-drafts/{d['id']}", headers=auth(org))
    assert r.status_code == 204
    assert (await api.get(f"/campaign-drafts/{d['id']}", headers=auth(org))).status_code == 404


async def test_list_drafts_only_shows_in_progress_ones_for_this_organisation(api):
    _, org = await signup(api, "organisation")
    _, other_org = await signup(api, "organisation")
    d1 = await _draft(api, org)
    d2 = await _draft(api, org)
    await api.patch(
        f"/campaign-drafts/{d2['id']}", headers=auth(org),
        json={
            "revision": 0, "title": "Done", "description": "x",
            "platforms": ["tiktok"], "payout_rule": {"rate_per_1000_views": 500}, "pot": 50000,
        },
    )
    await api.post(f"/campaign-drafts/{d2['id']}/finalize", headers=auth(org))
    await _draft(api, other_org)

    rows = (await api.get("/campaign-drafts", headers=auth(org))).json()
    assert [r["id"] for r in rows] == [d1["id"]]  # not the other org's, not the finalized one


async def test_a_creator_cannot_touch_campaign_drafts(api):
    _, creator = await signup(api, "creator")
    r = await api.post("/campaign-drafts", headers=auth(creator))
    assert r.status_code == 403


async def test_one_organisation_cannot_read_anothers_draft(api):
    _, org = await signup(api, "organisation")
    _, other_org = await signup(api, "organisation")
    d = await _draft(api, org)
    r = await api.get(f"/campaign-drafts/{d['id']}", headers=auth(other_org))
    assert r.status_code == 404
