"""The whole product, once, over HTTP: a brand funds a campaign, a creator
earns from it, and the money reaches a bank account.

If this passes, the seams between every module line up. Each step asserts
something the frontend actually shows.
"""

import json

from core.config import get_settings
from integrations.payments.sandbox import sign
from tests.http_app import (  # noqa: F401
    api, auth, clear_hold, db_session, earn, intel, latest_code, signup,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


async def test_a_brand_funds_a_campaign_a_creator_earns_and_is_paid(api, intel):
    # --- the brand signs up, confirms its email, onboards --------------------------------------
    _, brand = await signup(api, "organisation", verify=False)
    assert brand["user"]["email_verified"] is False and brand["user"]["onboarding_completed"] is False
    verified = await api.post("/auth/verify-email", headers=auth(brand), json={"code": latest_code(brand["user"]["email"])})
    assert verified.json()["email_verified"] is True
    logo = (await api.post("/uploads/images", headers=auth(brand), files={"file": ("l.png", PNG, "image/png")})).json()
    await api.put("/organisations/me/onboarding", headers=auth(brand), json={"name": "Indomie", "photo_upload_id": logo["id"], "budget_range": "₦250,000–₦750,000"})

    # --- builds a campaign the way the studio does -----------------------------------------------
    created = await api.post(
        "/campaigns", headers=auth(brand),
        json={
            "title": "No long thing", "tagline": "Turn the quickest meal into the clip nobody scrolls past.",
            "description": "A short, funny skit about hunger interrupting everything.", "category": "Comedy",
            "platforms": ["tiktok"], "pot": 500000, "duration_days": 14,
            "payout_rule": {"rate_per_1000_views": 500, "cap_amount": 75000, "min_views_threshold": 1000},
            "rules": [
                {"kind": "must", "text": "Show the prepared noodles clearly on screen."},
                {"kind": "avoid", "text": "Do not make health or nutrition claims."},
            ],
        },
    )
    assert created.status_code == 201, created.text
    campaign = created.json()
    assert campaign["phase"] == "Draft" and campaign["expected_views"] == 1_000_000 and campaign["brand"]["name"] == "Indomie"

    # --- funds it: order → "I have funded the pot" → live ---------------------------------------
    order = (await api.post(f"/campaigns/{campaign['slug']}/funding", headers=auth(brand), json={"method": "bank"})).json()
    assert order["total"] == 507_500 and order["campaign_status"] == "pending_funding"
    confirmed = (await api.post(f"/campaigns/{campaign['slug']}/funding/confirm", headers=auth(brand))).json()
    assert confirmed["status"] == "confirmed" and confirmed["campaign_status"] == "active"

    # --- a creator signs up, onboards, connects an account, finds the campaign ------------------
    creator_email, creator = await signup(api, "creator")
    await api.put("/creators/me/onboarding", headers=auth(creator), json={"display_name": "Tobi On Cam", "interests": ["Comedy"], "platforms": ["tiktok"]})
    from tests.http_app import connect_account

    await connect_account(creator["user"]["id"], "tiktok", "@tobioncam")

    feed = (await api.get("/campaigns?feed=for_you", headers=auth(creator))).json()
    assert [c["slug"] for c in feed] == [campaign["slug"]] and feed[0]["feed_status"] == "Open"
    detail = (await api.get(f"/campaigns/{campaign['slug']}", headers=auth(creator))).json()
    assert [r["kind"] for r in detail["rules"]] == ["must", "avoid"] and detail["metrics"] is None

    # --- submits a clip with the original video --------------------------------------------------
    video = (await api.post("/uploads/videos", headers=auth(creator), files={"file": ("clip.mp4", MP4, "video/mp4")})).json()
    sub = (
        await api.post(
            "/submissions", headers=auth(creator),
            json={"campaign_id": campaign["id"], "platform": "tiktok", "title": "Hunger interrupted the group chat",
                  "url": "https://www.tiktok.com/@tobioncam/video/7401234567890123456", "video_upload_id": video["id"]},
        )
    ).json()
    assert sub["verification"]["status"] == "needs_review"
    sid = sub["id"]

    # --- the brand sees it in its queue and approves it -------------------------------------------
    queue = (await api.get("/brand/reviews", headers=auth(brand))).json()
    assert queue["counts"]["needs_review"] == 1 and queue["items"][0]["creator_handle"] == "@tobioncam"
    assert (await api.post(f"/brand/reviews/{sid}/approve", headers=auth(brand), json={})).json()["status"] == "approved"
    assert any(n["title"] == "Your clip was approved" for n in (await api.get("/notifications", headers=auth(creator))).json()["items"])

    # --- views come in; settlement books them; the hold holds ------------------------------------------
    await earn(api, intel, sid, 12_400)
    money = (await api.get("/earnings/summary", headers=auth(creator))).json()
    assert money["in_hold"] == 6000 and money["payable"] == 0 and money["lifetime_views"] == 12_400
    live = (await api.get(f"/campaigns/{campaign['slug']}/stats", headers=auth(brand))).json()
    assert live["verified_views"] == 12_400 and live["spent"] == 6000 and live["remaining"] == 494_000 and live["approved"] == 1

    # --- five days pass; the creator adds a bank account and withdraws ----------------------------------
    await clear_hold(creator["user"]["id"])
    await api.put("/creators/me/bank-details", headers=auth(creator), json={"bank_code": "058", "bank_name": "Guaranty Trust Bank", "account_number": "0123456789"})
    assert (await api.post("/creators/me/bank-details/verify", headers=auth(creator))).json()["verified"] is True
    payout = (await api.post("/payouts", headers=auth(creator), json={"amount": 6000, "idempotency_key": "confirm-screen-e2e"})).json()
    assert payout["status"] == "succeeded" and payout["net"] == 6000 and payout["provenance"]["billable_views"] == 12_400

    money = (await api.get("/earnings/summary", headers=auth(creator))).json()
    assert money["payable"] == 0 and money["paid_all_time"] == 6000 and money["completed_payouts"] == 1
    history = (await api.get("/earnings/history", headers=auth(creator))).json()["items"]
    assert [(r["state"], r["amount"]) for r in history] == [("Paid", 6000)]

    # --- the brand's dashboards agree ------------------------------------------------------------------------------
    overview = (await api.get("/brand/overview", headers=auth(brand))).json()
    assert overview["live_campaigns"] == 1 and overview["total_spent"] == 6000 and overview["featured"]["metrics"]["earned"] == 6000
    board = (await api.get("/leaderboard?period=all", headers=auth(creator))).json()
    assert board["items"][0]["name"] == "Tobi On Cam" and board["me"]["rank"] == 1

    # --- and the paper trail is complete ---------------------------------------------------------------------------------
    from tests.http_app import make_admin

    admin = await make_admin(api)
    kinds = {e["kind"] for e in (await api.get("/admin/audit?limit=500", headers=auth(admin))).json()}
    assert {
        "campaign.created", "funding.order_created", "funding.confirmed", "campaign.opened", "submission.created",
        "submission.approved", "earnings.accrued", "payout.reserved", "payout.succeeded",
    } <= kinds
    assert (await api.get("/admin/overview", headers=auth(admin))).json()["creator_liability"] == 0
