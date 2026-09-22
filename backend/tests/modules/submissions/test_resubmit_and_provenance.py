"""Corrected resubmissions and per-entry earnings provenance
(production-api-inventory.md §I)."""

import pytest

from tests.http_app import (
    api, approve_clip, auth, campaign_body, clear_hold, earn, fund_campaign, intel, make_creator, signup, submit_clip,
)


async def _rejected_clip(api, org=None, creator=None):
    if org is None:
        _, org = await signup(api, "organisation")
    campaign = (await api.post(
        "/campaigns", headers=auth(org),
        json=campaign_body(rules=[{"kind": "must", "text": "Say the brand name out loud"}]),
    )).json()
    await fund_campaign(api, org, campaign["id"])
    if creator is None:
        creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await api.post(
        f"/brand/reviews/{sid}/request-correction", headers=auth(org),
        json={"reason": "Missing the brand name — please redo and resubmit."},
    )
    return org, creator, campaign, sid


async def test_resubmitting_a_rejected_clip_links_it_to_the_predecessor(api, intel):
    org, creator, campaign, sid = await _rejected_clip(api)

    corrected = await api.post(
        f"/submissions/{sid}/resubmit", headers=auth(creator),
        json={"platform": "tiktok", "url": "https://www.tiktok.com/@creator/video/999888777", "title": "Take 2"},
    )
    assert corrected.status_code == 201
    body = corrected.json()
    assert body["resubmitted_from_id"] == sid
    assert body["campaign_id"] == campaign["id"]

    # The original verdict is untouched.
    original = (await api.get(f"/submissions/{sid}", headers=auth(creator))).json()
    assert original["verification"]["status"] == "rejected"


async def test_a_clip_that_was_never_rejected_cannot_be_resubmitted(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]  # auto-approved: no rules

    r = await api.post(
        f"/submissions/{sid}/resubmit", headers=auth(creator),
        json={"platform": "tiktok", "url": "https://www.tiktok.com/@creator/video/1"},
    )
    assert r.status_code == 409


async def test_only_the_original_creator_can_resubmit(api, intel):
    org, creator, campaign, sid = await _rejected_clip(api)
    someone_else = await make_creator(api, handle="@someone_else")
    r = await api.post(
        f"/submissions/{sid}/resubmit", headers=auth(someone_else),
        json={"platform": "tiktok", "url": "https://www.tiktok.com/@x/video/1"},
    )
    # Same "don't confirm it exists" rule as every other submission route.
    assert r.status_code == 404


async def test_resubmission_chain_has_a_retry_limit(api, intel):
    org, creator, campaign, sid = await _rejected_clip(api)

    current = sid
    for i in range(2):  # two corrections on top of the original = the cap
        r = await api.post(
            f"/submissions/{current}/resubmit", headers=auth(creator),
            json={"platform": "tiktok", "url": f"https://www.tiktok.com/@creator/video/{1000 + i}"},
        )
        assert r.status_code == 201
        current = r.json()["id"]
        await api.post(
            f"/brand/reviews/{current}/request-correction", headers=auth(org),
            json={"reason": "Still missing the brand name."},
        )

    one_too_many = await api.post(
        f"/submissions/{current}/resubmit", headers=auth(creator),
        json={"platform": "tiktok", "url": "https://www.tiktok.com/@creator/video/9999"},
    )
    assert one_too_many.status_code == 409


async def test_earning_entry_detail_traces_the_amount_to_a_snapshot(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post(
        "/campaigns", headers=auth(org),
        json=campaign_body(expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0}),
    )).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await approve_clip(api, org, sid)
    await earn(api, intel, sid, 12_000)  # ₦6,000

    history = (await api.get("/earnings/history", headers=auth(creator))).json()
    entry_id = history["items"][0]["id"]

    detail = await api.get(f"/earnings/entries/{entry_id}", headers=auth(creator))
    assert detail.status_code == 200
    body = detail.json()
    assert body["submission_id"] == sid and body["campaign_id"] == campaign["id"]
    assert body["thousands"] == 12 and body["amount"] == 6000
    assert body["rate_per_1000_views"] == 500 and body["state"] == "Accrued"
    assert body["reference"] == f"{sid}:12"

    await clear_hold(creator["user"]["id"])
    cleared = (await api.get(f"/earnings/entries/{entry_id}", headers=auth(creator))).json()
    assert cleared["state"] == "Payable"


async def test_a_creator_cannot_read_another_creators_earning_entry(api, intel):
    _, org = await signup(api, "organisation")
    campaign = (await api.post(
        "/campaigns", headers=auth(org),
        json=campaign_body(expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0}),
    )).json()
    await fund_campaign(api, org, campaign["id"])
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    await approve_clip(api, org, sid)
    await earn(api, intel, sid, 5_000)
    entry_id = (await api.get("/earnings/history", headers=auth(creator))).json()["items"][0]["id"]

    intruder = await make_creator(api, handle="@intruder")
    r = await api.get(f"/earnings/entries/{entry_id}", headers=auth(intruder))
    assert r.status_code == 404


async def test_an_unknown_entry_is_404(api):
    _, creator = await signup(api, "creator")
    r = await api.get("/earnings/entries/00000000-0000-0000-0000-000000000000", headers=auth(creator))
    assert r.status_code == 404
