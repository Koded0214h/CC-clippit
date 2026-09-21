import uuid

from tests.http_app import (  # noqa: F401
    api, auth, connect_account, db_session, intel, make_creator, open_campaign, signup, submit_clip,
)

MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64
RULES = [
    {"kind": "must", "text": "Show the prepared noodles clearly on screen."},
    {"kind": "must", "text": "Say or display: No long thing."},
    {"kind": "avoid", "text": "Do not make health or nutrition claims."},
]


async def _live(api, org, **kw):
    return await open_campaign(api, org, rules=RULES, **kw)


async def test_a_submission_is_registered_then_queued_for_review(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await _live(api, org)
    creator = await make_creator(api)

    r = await submit_clip(api, creator, campaign["id"], title="Hunger interrupted the group chat")
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["title"] == "Hunger interrupted the group chat" and s["status"] == "submitted"
    assert s["campaign"]["slug"] == campaign["slug"]

    v = s["verification"]
    assert v["status"] == "needs_review" and v["total"] == 3 and v["passed"] == 0
    assert [x["verdict"] for x in v["requirements"]] == ["review"] * 3
    assert v["decided_by_human"] is False and v["confidence"] is None
    steps = {st["key"]: st["state"] for st in v["steps"]}
    assert steps == {"post_ownership": "done", "brief_requirements": "active", "trust_signals": "pending", "first_reading": "pending"}

    # Intelligence was handed exactly the contract's SubmissionRef.
    ref = intel.registered[0]
    assert ref["submission_id"] == s["id"] and ref["campaign_id"] == campaign["id"] and ref["platform"] == "tiktok"


async def test_the_brand_is_told_a_clip_needs_review(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await _live(api, org)
    creator = await make_creator(api)
    sub = (await submit_clip(api, creator, campaign["id"])).json()
    inbox = (await api.get("/notifications", headers=auth(org))).json()["items"]
    review = [n for n in inbox if n["kind"] == "review_needed"]
    assert len(review) == 1 and review[0]["link"] == f"/brand/reviews/{sub['id']}"


async def test_a_campaign_with_no_requirements_approves_outright(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org)  # no rules
    creator = await make_creator(api)
    s = (await submit_clip(api, creator, campaign["id"])).json()
    assert s["verification"]["status"] == "approved" and s["verification"]["total"] == 0
    assert s["verification"]["decided_by_human"] is False


async def test_a_rejected_link_is_kept_with_the_reason_and_the_error_reaches_the_creator(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await _live(api, org)
    creator = await make_creator(api)
    intel.fail_register = (422, {"code": "url_not_recognised", "message": "That isn't a post link."})

    r = await submit_clip(api, creator, campaign["id"], url="https://example.com/nope")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "url_not_recognised"

    mine = (await api.get("/submissions", headers=auth(creator))).json()
    assert len(mine) == 1
    kept = mine[0]
    assert kept["status"] == "rejected" and kept["rejection_code"] == "url_not_recognised"
    assert kept["verification"]["status"] == "rejected"
    # It never reaches the brand's review queue: there is nothing to review.
    queue = (await api.get("/brand/reviews", headers=auth(org))).json()
    assert queue["counts"]["needs_review"] == 0


async def test_intelligence_being_down_creates_nothing(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await _live(api, org)
    creator = await make_creator(api)
    intel.unreachable = True
    r = await submit_clip(api, creator, campaign["id"])
    assert r.status_code == 502
    assert (await api.get("/submissions", headers=auth(creator))).json() == []


async def test_a_paused_campaign_refuses_new_clips_but_a_resumed_one_takes_them(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await _live(api, org)
    creator = await make_creator(api)
    await api.post(f"/campaigns/{campaign['id']}/pause", headers=auth(org))
    r = await submit_clip(api, creator, campaign["id"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "campaign_not_accepting"
    await api.post(f"/campaigns/{campaign['id']}/resume", headers=auth(org))
    assert (await submit_clip(api, creator, campaign["id"])).status_code == 201


async def test_closed_and_draft_campaigns_take_no_clips(api, intel):
    _, org = await signup(api, "organisation")
    creator = await make_creator(api)
    closed = await _live(api, org, title="Closed one")
    await api.post(f"/campaigns/{closed['id']}/close", headers=auth(org))
    assert (await submit_clip(api, creator, closed["id"])).status_code == 404
    draft = (await api.post("/campaigns", headers=auth(org), json={"title": "d", "description": "d", "expected_views": 10, "platforms": ["tiktok"], "payout_rule": {"rate_per_1000_views": 1}})).json()
    assert (await submit_clip(api, creator, draft["id"])).status_code == 404


async def test_a_deadline_that_has_passed_refuses_clips(api, intel):
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from modules.campaigns.models import Campaign

    _, org = await signup(api, "organisation")
    campaign = await _live(api, org)
    creator = await make_creator(api)
    async with db_session() as db:
        row = await db.scalar(select(Campaign).where(Campaign.id == campaign["id"]))
        row.ends_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db.commit()
    r = await submit_clip(api, creator, campaign["id"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "campaign_not_accepting"


async def test_platform_and_account_and_role_guards(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await _live(api, org)
    creator = await make_creator(api)
    assert (await submit_clip(api, creator, campaign["id"], platform="instagram")).status_code == 422  # not on the campaign
    stranger = (await signup(api, "creator"))[1]  # verified, but nothing connected
    r = await submit_clip(api, stranger, campaign["id"])
    assert r.status_code == 409 and "Connect" in r.json()["detail"]
    assert (await submit_clip(api, org, campaign["id"])).status_code == 403
    unverified = (await signup(api, "creator", verify=False))[1]
    r = await submit_clip(api, unverified, campaign["id"])
    assert r.status_code == 403 and r.json()["detail"]["code"] == "email_not_verified"


async def test_the_original_video_must_be_the_creators_own_video(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await _live(api, org)
    creator = await make_creator(api)
    other = await make_creator(api)
    vid = (await api.post("/uploads/videos", headers=auth(other), files={"file": ("a.mp4", MP4, "video/mp4")})).json()["id"]
    assert (await submit_clip(api, creator, campaign["id"], video_upload_id=vid)).status_code == 422  # someone else's
    mine = (await api.post("/uploads/videos", headers=auth(creator), files={"file": ("a.mp4", MP4, "video/mp4")})).json()
    ok = await submit_clip(api, creator, campaign["id"], video_upload_id=mine["id"])
    assert ok.status_code == 201 and ok.json()["video_url"] == mine["url"]


async def test_visibility_is_creator_owner_brand_admin_only(api, intel):
    _, org = await signup(api, "organisation")
    _, rival = await signup(api, "organisation")
    campaign = await _live(api, org)
    creator = await make_creator(api)
    stranger = await make_creator(api)
    sub = (await submit_clip(api, creator, campaign["id"])).json()

    assert (await api.get(f"/submissions/{sub['id']}", headers=auth(creator))).status_code == 200
    assert (await api.get(f"/submissions/{sub['id']}", headers=auth(org))).status_code == 200
    for outsider in (stranger, rival):
        assert (await api.get(f"/submissions/{sub['id']}", headers=auth(outsider))).status_code == 404
        assert (await api.get("/submissions", headers=auth(outsider))).json() == []


async def test_withdraw_stops_tracking_and_keeps_an_audit_trail(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await _live(api, org)
    creator = await make_creator(api)
    sub = (await submit_clip(api, creator, campaign["id"])).json()

    r = await api.post(f"/submissions/{sub['id']}/withdraw", headers=auth(creator))
    assert r.status_code == 200 and r.json()["status"] == "withdrawn"
    assert sub["id"] in intel.stopped
    assert (await api.post(f"/submissions/{sub['id']}/withdraw", headers=auth(creator))).status_code == 409
    assert (await api.post(f"/submissions/{sub['id']}/withdraw", headers=auth(org))).status_code == 403


async def test_list_filters_by_verification_status(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await _live(api, org)
    creator = await make_creator(api)
    await submit_clip(api, creator, campaign["id"])
    assert len((await api.get("/submissions?verification=needs_review", headers=auth(creator))).json()) == 1
    assert (await api.get("/submissions?verification=approved", headers=auth(creator))).json() == []


async def test_the_performance_proxy_is_visibility_checked(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await _live(api, org)
    creator = await make_creator(api)
    stranger = await make_creator(api)
    sub = (await submit_clip(api, creator, campaign["id"])).json()
    intel.set_views(sub["id"], 4200)
    r = await api.get(f"/submissions/{sub['id']}/performance", headers=auth(creator))
    assert r.status_code == 200 and r.json()["metrics"]["views"] == 4200
    assert (await api.get(f"/submissions/{sub['id']}/performance", headers=auth(stranger))).status_code == 404
