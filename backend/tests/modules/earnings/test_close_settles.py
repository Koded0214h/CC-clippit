from decimal import Decimal

from sqlalchemy import func, select

from modules.earnings.models import EarningEntry
from tests.http_app import api, auth, db_session, earn, intel, make_creator, open_campaign, signup, submit_clip  # noqa: F401


async def test_closing_a_campaign_books_the_views_earned_so_far(api, intel):
    _, org = await signup(api, "organisation")
    campaign = await open_campaign(api, org, expected_views=1_000_000, payout_rule={"rate_per_1000_views": 500, "min_views_threshold": 0})
    creator = await make_creator(api)
    sid = (await submit_clip(api, creator, campaign["id"])).json()["id"]
    intel.set_views(sid, 4000)  # read by Intelligence but not yet settled

    closed = await api.post(f"/campaigns/{campaign['id']}/close", headers=auth(org))
    assert closed.json()["status"] == "closed"
    async with db_session() as db:
        total = await db.scalar(select(func.coalesce(func.sum(EarningEntry.amount), 0)).where(EarningEntry.campaign_id == campaign["id"]))
    assert total == Decimal("2000.00")  # 4 thousand × ₦500, not forfeited
    assert sid in intel.stopped
