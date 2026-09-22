"""The resumable onboarding lifecycle (production-api-inventory.md §C):
GET/PATCH autosave/complete/reset, alongside the older one-shot PUT."""

import pytest

from tests.http_app import api, auth, signup


async def test_a_fresh_creator_starts_not_started(api):
    _, creator = await signup(api, "creator")
    r = await api.get("/creators/me/onboarding", headers=auth(creator))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "not_started" and body["revision"] == 0 and body["answers"] == {}


async def test_autosave_accumulates_answers_across_screens_and_bumps_revision(api):
    _, creator = await signup(api, "creator")
    step1 = await api.patch(
        "/creators/me/onboarding", headers=auth(creator),
        json={"revision": 0, "step": "name", "display_name": "Tobi"},
    )
    assert step1.status_code == 200
    body = step1.json()
    assert body["status"] == "in_progress" and body["revision"] == 1 and body["answers"]["display_name"] == "Tobi"

    step2 = await api.patch(
        "/creators/me/onboarding", headers=auth(creator),
        json={"revision": 1, "step": "lanes", "interests": ["comedy", "music"]},
    )
    assert step2.status_code == 200
    merged = step2.json()["answers"]
    assert merged["display_name"] == "Tobi" and merged["interests"] == ["comedy", "music"]


async def test_a_stale_revision_is_refused_not_silently_overwritten(api):
    _, creator = await signup(api, "creator")
    await api.patch("/creators/me/onboarding", headers=auth(creator), json={"revision": 0, "display_name": "Tobi"})
    stale = await api.patch("/creators/me/onboarding", headers=auth(creator), json={"revision": 0, "display_name": "Someone else"})
    assert stale.status_code == 409
    current = (await api.get("/creators/me/onboarding", headers=auth(creator))).json()
    assert current["answers"]["display_name"] == "Tobi"


async def test_complete_needs_every_required_answer_and_is_not_marked_complete_by_patch(api):
    _, creator = await signup(api, "creator")
    await api.patch("/creators/me/onboarding", headers=auth(creator), json={"revision": 0, "display_name": "Tobi"})
    still_draft = (await api.get("/creators/me/onboarding", headers=auth(creator))).json()
    assert still_draft["status"] == "in_progress"  # PATCH alone never completes it

    incomplete = await api.post("/creators/me/onboarding/complete", headers=auth(creator))
    assert incomplete.status_code == 422  # missing required `interests`

    await api.patch("/creators/me/onboarding", headers=auth(creator), json={"revision": 1, "interests": ["comedy"]})
    done = await api.post("/creators/me/onboarding/complete", headers=auth(creator))
    assert done.status_code == 200
    profile = done.json()
    assert profile["display_name"] == "Tobi" and profile["interests"] == ["comedy"] and profile["onboarding_completed"] is True

    status_after = (await api.get("/creators/me/onboarding", headers=auth(creator))).json()
    assert status_after["status"] == "completed" and status_after["answers"] == {}


async def test_complete_is_idempotent_and_does_not_re_validate_a_cleared_draft(api):
    _, creator = await signup(api, "creator")
    await api.patch("/creators/me/onboarding", headers=auth(creator), json={"revision": 0, "display_name": "Tobi", "interests": ["comedy"]})
    first = await api.post("/creators/me/onboarding/complete", headers=auth(creator))
    assert first.status_code == 200
    again = await api.post("/creators/me/onboarding/complete", headers=auth(creator))
    assert again.status_code == 200 and again.json() == first.json()


async def test_resetting_an_incomplete_draft_clears_it_but_never_the_account(api):
    _, creator = await signup(api, "creator")
    await api.patch("/creators/me/onboarding", headers=auth(creator), json={"revision": 0, "display_name": "Tobi"})
    reset = await api.delete("/creators/me/onboarding/draft", headers=auth(creator))
    assert reset.status_code == 204
    after = (await api.get("/creators/me/onboarding", headers=auth(creator))).json()
    assert after["status"] == "not_started" and after["answers"] == {}
    me = (await api.get("/auth/me", headers=auth(creator))).json()
    assert me["email"]  # the account is untouched


async def test_reset_after_completion_is_refused(api):
    _, creator = await signup(api, "creator")
    await api.patch("/creators/me/onboarding", headers=auth(creator), json={"revision": 0, "display_name": "Tobi", "interests": ["comedy"]})
    await api.post("/creators/me/onboarding/complete", headers=auth(creator))
    r = await api.delete("/creators/me/onboarding/draft", headers=auth(creator))
    assert r.status_code == 409


async def test_organisation_accounts_use_their_own_draft_and_branch(api):
    _, org = await signup(api, "organisation")
    r = await api.get("/organisations/me/onboarding", headers=auth(org))
    assert r.status_code == 200 and r.json()["status"] == "not_started"

    await api.patch("/organisations/me/onboarding", headers=auth(org), json={"revision": 0, "name": "Holiday Heartbreaks"})
    done = await api.post("/organisations/me/onboarding/complete", headers=auth(org))
    assert done.status_code == 200 and done.json()["name"] == "Holiday Heartbreaks"


async def test_an_organisation_cannot_read_a_creators_draft_endpoint(api):
    _, org = await signup(api, "organisation")
    r = await api.get("/creators/me/onboarding", headers=auth(org))
    assert r.status_code == 403
