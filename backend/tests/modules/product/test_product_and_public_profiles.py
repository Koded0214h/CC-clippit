"""Product config, handle availability, public profiles, and legal
acceptances (production-api-inventory.md §D, §R)."""

import pytest

from tests.http_app import (
    api, approve_clip, auth, campaign_body, fund_campaign, intel, make_creator, signup, submit_clip,
)


async def test_product_config_is_public_and_shapes_the_client_needs(api):
    r = await api.get("/product-config")
    assert r.status_code == 200
    body = r.json()
    assert body["hold_days"] == 5 and body["currency"] == "NGN"
    assert any(p["platform"] == "tiktok" and p["connectable"] for p in body["platforms"])
    assert any(p["platform"] == "youtube" and not p["connectable"] for p in body["platforms"])
    assert body["campaign_limits"]["max_duration_days"] == 90
    assert {d["slug"] for d in body["legal"]} >= {"terms", "privacy"}


async def test_handle_availability_checks_shape_and_the_shared_namespace(api):
    invalid = await api.get("/handles/a b/availability")
    assert invalid.json()["available"] is False and invalid.json()["reason"] == "invalid"

    _, creator = await signup(api, "creator")
    await api.put("/creators/me/profile", headers=auth(creator), json={"handle": "tobi_makes"})

    taken = await api.get("/handles/tobi_makes/availability")
    assert taken.json() == {"handle": "tobi_makes", "available": False, "reason": "taken"}

    free = await api.get("/handles/tobi_unclaimed/availability")
    assert free.json()["available"] is True


async def test_a_handle_cannot_be_taken_twice_across_creators_and_organisations(api):
    _, creator = await signup(api, "creator")
    await api.put("/creators/me/profile", headers=auth(creator), json={"handle": "sameword"})

    _, org = await signup(api, "organisation")
    collide = await api.put("/organisations/me/profile", headers=auth(org), json={"slug": "sameword"})
    assert collide.status_code == 409


async def test_public_creator_profile_shows_approved_work_and_hides_a_private_one(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post(
        "/campaigns", headers=auth(org),
        json=campaign_body(rules=[{"kind": "must", "text": "Say the brand name out loud"}]),
    )).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    await api.put("/creators/me/profile", headers=auth(creator), json={"handle": "tobi_public", "bio": "I make clips"})
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await approve_clip(api, org, sid)

    r = await api.get("/profiles/creators/tobi_public")
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"] and body["bio"] == "I make clips"
    assert body["stats"]["approved_clips"] == 1
    assert body["recent_work"][0]["campaign_slug"] == campaign["slug"]

    clips = (await api.get("/profiles/creators/tobi_public/clips")).json()
    assert len(clips) == 1

    await api.put("/creators/me/profile", headers=auth(creator), json={"public_profile": False})
    hidden = await api.get("/profiles/creators/tobi_public")
    assert hidden.status_code == 404


async def test_a_creator_with_no_handle_has_no_public_profile(api):
    r = await api.get("/profiles/creators/nobody-has-this-handle")
    assert r.status_code == 404


async def test_public_organisation_profile_counts_live_and_completed_campaigns(api):
    _, org = await signup(api, "organisation")
    await api.put("/organisations/me/profile", headers=auth(org), json={"slug": "acme-drinks", "website": "https://acme.example"})
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    await fund_campaign(api, org, campaign["id"])

    r = await api.get("/profiles/organisations/acme-drinks")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] and body["website"] == "https://acme.example"
    assert body["campaigns"]["live_campaigns"] == 1 and body["campaigns"]["completed_campaigns"] == 0


async def test_legal_documents_and_acceptances_round_trip(api):
    doc = (await api.get("/legal/documents/terms")).json()
    assert doc["slug"] == "terms" and doc["version"]

    missing = await api.get("/legal/documents/no-such-doc")
    assert missing.status_code == 404

    _, creator = await signup(api, "creator")
    before = (await api.get("/legal/acceptances/me", headers=auth(creator))).json()
    assert "terms" in before["newly_required"]

    accepted = await api.post(
        "/legal/acceptances", headers=auth(creator),
        json={"slug": "terms", "version": doc["version"], "action": "signup"},
    )
    assert accepted.status_code == 201

    after = (await api.get("/legal/acceptances/me", headers=auth(creator))).json()
    assert "terms" not in after["newly_required"]
    assert any(a["slug"] == "terms" for a in after["accepted"])

    # Idempotent: accepting the same version twice doesn't duplicate.
    again = await api.post(
        "/legal/acceptances", headers=auth(creator),
        json={"slug": "terms", "version": doc["version"], "action": "signup"},
    )
    assert again.status_code == 201
    final = (await api.get("/legal/acceptances/me", headers=auth(creator))).json()
    assert len([a for a in final["accepted"] if a["slug"] == "terms"]) == 1


async def test_accepting_a_stale_version_is_refused(api):
    _, creator = await signup(api, "creator")
    r = await api.post(
        "/legal/acceptances", headers=auth(creator),
        json={"slug": "terms", "version": "0", "action": "signup"},
    )
    assert r.status_code == 409
