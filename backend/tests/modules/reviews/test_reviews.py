from tests.http_app import (  # noqa: F401
    api, approve_clip, auth, intel, make_creator, open_campaign, signup, submit_clip,
)

RULES = [
    {"kind": "must", "text": "Show the prepared noodles clearly on screen."},
    {"kind": "must", "text": "Tag @indomie_nigeria and use #NoLongThing."},
]
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


async def _setup(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org, rules=RULES)
    creator = await make_creator(api, handle="@kemiframes")
    await api.put("/creators/me/profile", headers=auth(creator), json={"display_name": "Kemi Frames"})
    sub = (await submit_clip(api, creator, campaign["id"], title="When hunger joins the call")).json()
    return org, campaign, creator, sub


async def test_the_queue_lists_clips_with_who_and_why_and_counts(api, intel):
    org, campaign, creator, sub = await _setup(api, intel)
    q = (await api.get("/brand/reviews", headers=auth(org))).json()
    assert q["tab"] == "needs_review" and q["counts"] == {"needs_review": 1, "appeals": 0, "resolved": 0}
    card = q["items"][0]
    assert card["id"] == sub["id"] and card["creator_name"] == "Kemi Frames" and card["creator_handle"] == "@kemiframes"
    assert card["campaign_slug"] == campaign["slug"] and card["platform"] == "tiktok"
    assert card["issue"] and card["is_appeal"] is False and card["confidence"] is None


async def test_only_the_owning_brand_and_admin_see_the_queue(api, intel):
    org, campaign, creator, sub = await _setup(api, intel)
    _, rival = await signup(api, "organisation")
    assert (await api.get("/brand/reviews", headers=auth(rival))).json()["items"] == []
    assert (await api.get(f"/brand/reviews/{sub['id']}", headers=auth(rival))).status_code == 404
    assert (await api.post(f"/brand/reviews/{sub['id']}/approve", headers=auth(rival), json={})).status_code == 404
    assert (await api.get("/brand/reviews", headers=auth(creator))).status_code == 403


async def test_detail_shows_each_requirement_and_what_is_flagged(api, intel):
    org, campaign, creator, sub = await _setup(api, intel)
    d = (await api.get(f"/brand/reviews/{sub['id']}", headers=auth(org))).json()
    assert d["total"] == 2 and d["passed"] == 0
    assert d["requirements"][0]["text"] == RULES[0]["text"]
    assert d["flagged_requirement"]["id"] == d["requirements"][0]["id"]
    assert d["creator_id"] == sub["creator_id"] and d["appeal"] is None


async def test_approving_passes_every_requirement_and_tells_the_creator(api, intel):
    org, campaign, creator, sub = await _setup(api, intel)
    r = await approve_clip(api, org, sub["id"])
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "approved" and d["passed"] == 2 and d["decided_by_human"] is True

    mine = (await api.get(f"/submissions/{sub['id']}", headers=auth(creator))).json()["verification"]
    assert mine["status"] == "approved" and mine["passed"] == 2 and mine["verdict_at"]
    assert {s["key"]: s["state"] for s in mine["steps"]}["brief_requirements"] == "done"

    inbox = (await api.get("/notifications", headers=auth(creator))).json()["items"]
    assert any(n["kind"] == "submission_verdict" and "approved" in n["title"] for n in inbox)
    # It moves to the "resolved" tab, out of "needs review".
    counts = (await api.get("/brand/reviews", headers=auth(org))).json()["counts"]
    assert counts == {"needs_review": 0, "appeals": 0, "resolved": 1}
    assert (await approve_clip(api, org, sub["id"])).status_code == 409  # already decided


async def test_requesting_a_correction_names_the_failed_requirement(api, intel):
    org, campaign, creator, sub = await _setup(api, intel)
    target = sub["verification"]["requirements"][1]
    r = await api.post(
        f"/brand/reviews/{sub['id']}/request-correction",
        headers=auth(org),
        json={"reason": "The campaign tag is missing from the caption.", "requirement_id": target["id"]},
    )
    assert r.status_code == 200 and r.json()["status"] == "rejected"

    v = (await api.get(f"/submissions/{sub['id']}", headers=auth(creator))).json()["verification"]
    assert v["status"] == "rejected" and v["summary"] == "The campaign tag is missing from the caption."
    assert v["failed_requirement"]["id"] == target["id"] and v["failed_requirement"]["note"] == v["summary"]
    assert v["passed"] == 0 and v["total"] == 2
    inbox = (await api.get("/notifications", headers=auth(creator))).json()["items"]
    assert any("Correction needed" in n["title"] for n in inbox)


async def test_a_correction_without_a_named_requirement_flags_the_first_pending_one(api, intel):
    org, campaign, creator, sub = await _setup(api, intel)
    await api.post(f"/brand/reviews/{sub['id']}/request-correction", headers=auth(org), json={"reason": "The pack is hidden."})
    v = (await api.get(f"/submissions/{sub['id']}", headers=auth(creator))).json()["verification"]
    assert v["failed_requirement"]["text"] == RULES[0]["text"]


async def test_a_requirement_from_another_submission_is_refused(api, intel):
    org, campaign, creator, sub = await _setup(api, intel)
    r = await api.post(
        f"/brand/reviews/{sub['id']}/request-correction", headers=auth(org),
        json={"reason": "Nope, wrong id here.", "requirement_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert r.status_code == 409


async def test_a_short_reason_is_refused(api, intel):
    org, campaign, creator, sub = await _setup(api, intel)
    assert (await api.post(f"/brand/reviews/{sub['id']}/request-correction", headers=auth(org), json={"reason": "no"})).status_code == 422


# --- appeals ----------------------------------------------------------------------------------


async def _rejected(api, intel):
    org, campaign, creator, sub = await _setup(api, intel)
    await api.post(f"/brand/reviews/{sub['id']}/request-correction", headers=auth(org), json={"reason": "Tag @indomie_nigeria is missing."})
    return org, campaign, creator, sub


async def test_appeal_moves_the_clip_to_the_appeals_tab_with_the_reason(api, intel):
    org, campaign, creator, sub = await _rejected(api, intel)
    evidence = (await api.post("/uploads/evidence", headers=auth(creator), files={"file": ("s.png", PNG, "image/png")})).json()
    r = await api.post(
        f"/submissions/{sub['id']}/appeal", headers=auth(creator),
        json={"reason": "The tag is in the expanded caption, please check.", "evidence_upload_id": evidence["id"]},
    )
    assert r.status_code == 201, r.text
    v = r.json()["verification"]
    assert v["status"] == "appealed" and v["appeal"]["status"] == "open" and v["appeal"]["evidence_url"] == evidence["url"]

    q = (await api.get("/brand/reviews?tab=appeals", headers=auth(org))).json()
    assert q["counts"]["appeals"] == 1 and q["items"][0]["is_appeal"] is True
    d = (await api.get(f"/brand/reviews/{sub['id']}", headers=auth(org))).json()
    assert d["appeal"]["reason"].startswith("The tag is in the expanded caption")


async def test_upholding_an_appeal_overturns_the_rejection_when_approved(api, intel):
    org, campaign, creator, sub = await _rejected(api, intel)
    await api.post(f"/submissions/{sub['id']}/appeal", headers=auth(creator), json={"reason": "The tag is in the expanded caption, honest."})
    r = await approve_clip(api, org, sub["id"])
    assert r.status_code == 200 and r.json()["status"] == "approved"
    v = (await api.get(f"/submissions/{sub['id']}", headers=auth(creator))).json()["verification"]
    assert v["appeal"]["status"] == "overturned" and v["passed"] == v["total"]
    inbox = (await api.get("/notifications", headers=auth(creator))).json()["items"]
    assert any(n["kind"] == "appeal_decision" and "Appeal upheld" in n["title"] for n in inbox)


async def test_rejecting_again_leaves_the_original_decision_standing(api, intel):
    org, campaign, creator, sub = await _rejected(api, intel)
    await api.post(f"/submissions/{sub['id']}/appeal", headers=auth(creator), json={"reason": "I really did include the tag in it."})
    r = await api.post(f"/brand/reviews/{sub['id']}/request-correction", headers=auth(org), json={"reason": "Checked: the tag is not there."})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    v = (await api.get(f"/submissions/{sub['id']}", headers=auth(creator))).json()["verification"]
    assert v["appeal"]["status"] == "upheld" and v["appeal"]["decision_note"] == "Checked: the tag is not there."
    # One appeal per verdict: asking the same question twice is refused.
    again = await api.post(f"/submissions/{sub['id']}/appeal", headers=auth(creator), json={"reason": "Please look at it one more time."})
    assert again.status_code == 409


async def test_only_a_rejected_clip_can_be_appealed_and_only_by_its_creator(api, intel):
    org, campaign, creator, sub = await _setup(api, intel)  # still needs_review
    long_reason = {"reason": "This is a reason that is long enough."}
    assert (await api.post(f"/submissions/{sub['id']}/appeal", headers=auth(creator), json=long_reason)).status_code == 409
    await api.post(f"/brand/reviews/{sub['id']}/request-correction", headers=auth(org), json={"reason": "The tag is missing."})
    stranger = await make_creator(api)
    assert (await api.post(f"/submissions/{sub['id']}/appeal", headers=auth(stranger), json=long_reason)).status_code == 404
    assert (await api.post(f"/submissions/{sub['id']}/appeal", headers=auth(org), json=long_reason)).status_code == 403
    assert (await api.post(f"/submissions/{sub['id']}/appeal", headers=auth(creator), json={"reason": "too short"})).status_code == 422


async def test_the_brand_is_told_when_a_creator_appeals(api, intel):
    org, campaign, creator, sub = await _rejected(api, intel)
    await api.post(f"/submissions/{sub['id']}/appeal", headers=auth(creator), json={"reason": "The tag is in the expanded caption."})
    titles = [n["title"] for n in (await api.get("/notifications", headers=auth(org))).json()["items"]]
    assert "A creator appealed a verdict" in titles


async def test_evidence_must_be_the_creators_own(api, intel):
    org, campaign, creator, sub = await _rejected(api, intel)
    other = await make_creator(api)
    theirs = (await api.post("/uploads/evidence", headers=auth(other), files={"file": ("s.png", PNG, "image/png")})).json()
    r = await api.post(
        f"/submissions/{sub['id']}/appeal", headers=auth(creator),
        json={"reason": "The tag is in the expanded caption.", "evidence_upload_id": theirs["id"]},
    )
    assert r.status_code == 422


async def test_resolved_tab_only_holds_human_decisions(api, intel):
    _, org = await signup(api, "organisation")
    auto = await open_campaign(api, org)  # no rules → approved by the system
    creator = await make_creator(api)
    await submit_clip(api, creator, auto["id"])
    counts = (await api.get("/brand/reviews", headers=auth(org))).json()["counts"]
    assert counts == {"needs_review": 0, "appeals": 0, "resolved": 0}
