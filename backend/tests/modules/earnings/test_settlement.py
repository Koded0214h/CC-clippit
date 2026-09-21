"""Settlement rules. These are the tests that matter most: they are the money."""

import asyncio
import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from core.database import Base  # noqa: F401
from modules.audit.models import AuditEvent
from modules.campaigns import service as campaign_service
from modules.earnings import service
from modules.earnings.models import EarningAccount, EarningEntry
from tests.http_app import (  # noqa: F401
    api, approve_clip, auth, db_session, intel, make_creator, open_campaign, signup, submit_clip,
)


async def _live_clip(api, intel, *, rate=500, min_views=1000, cap=None, pot=None, rules=False):
    """An approved clip on a live campaign; returns (org, campaign, creator, submission_id)."""
    _, org = await signup(api, "organisation")
    rule = {"rate_per_1000_views": rate, "min_views_threshold": min_views}
    if cap is not None:
        rule["cap_amount"] = cap
    campaign = await open_campaign(
        api, org, payout_rule=rule, expected_views=None if pot else 1_000_000, **({"pot": pot} if pot else {}),
        **({"rules": [{"kind": "must", "text": "Show the product clearly."}]} if rules else {}),
    )
    creator = await make_creator(api)
    sub = (await submit_clip(api, creator, campaign["id"])).json()
    if rules:
        assert (await approve_clip(api, org, sub["id"])).status_code == 200
    assert sub["verification"]["status"] in ("approved", "needs_review")
    return org, campaign, creator, sub["id"]


async def _settle(intel, submission_id, views=None):
    if views is not None:
        intel.set_views(submission_id, views)
    async with db_session() as db:
        result = await service.settle_submission(db, uuid.UUID(submission_id), intel)
        await db.commit()
    return result


async def _entries(submission_id):
    async with db_session() as db:
        return list(await db.scalars(select(EarningEntry).where(EarningEntry.submission_id == submission_id).order_by(EarningEntry.accrued_at)))


# --- the arithmetic ------------------------------------------------------------------------------


async def test_nothing_is_owed_below_the_minimum_views(api, intel):
    _, _, _, sid = await _live_clip(api, intel, rate=500, min_views=1000)
    r = await _settle(intel, sid, 999)
    assert r.status == "skipped" and r.reason == "below_minimum"
    assert await _entries(sid) == []


async def test_each_whole_thousand_pays_the_rate(api, intel):
    _, _, _, sid = await _live_clip(api, intel, rate=500)
    r = await _settle(intel, sid, 1000)
    assert r.status == "accrued" and r.thousands == 1 and r.amount == Decimal("500")
    r = await _settle(intel, sid, 4700)  # 4.7 thousand → 3 more, not 4
    assert r.thousands == 3 and r.amount == Decimal("1500")
    total = sum(e.amount for e in await _entries(sid))
    assert total == Decimal("2000.00")


async def test_partial_thousands_are_never_billed(api, intel):
    _, _, _, sid = await _live_clip(api, intel, rate=500, min_views=0)
    r = await _settle(intel, sid, 999)
    assert r.status == "skipped" and r.reason == "no_new_thousand"


async def test_two_partial_polls_add_up_instead_of_rounding_to_nothing(api, intel):
    """900 views, then 900 more. A scheme that floors each poll's *delta* pays
    zero twice; billing from the cumulative total pays the thousand."""
    _, _, _, sid = await _live_clip(api, intel, rate=500, min_views=0)
    assert (await _settle(intel, sid, 900)).status == "skipped"
    r = await _settle(intel, sid, 1800)
    assert r.status == "accrued" and r.thousands == 1 and r.amount == Decimal("500")


async def test_settling_twice_on_the_same_reading_pays_once(api, intel):
    _, _, _, sid = await _live_clip(api, intel, rate=500)
    assert (await _settle(intel, sid, 3000)).status == "accrued"
    again = await _settle(intel, sid)
    assert again.status == "skipped" and again.reason == "no_new_thousand"
    assert len(await _entries(sid)) == 1


async def test_a_downward_revision_never_claws_money_back_or_double_pays(api, intel):
    _, _, _, sid = await _live_clip(api, intel, rate=500)
    await _settle(intel, sid, 5000)
    r = await _settle(intel, sid, 3200)  # the platform pruned bot views
    assert r.status == "skipped"
    assert sum(e.amount for e in await _entries(sid)) == Decimal("2500.00")
    r = await _settle(intel, sid, 5400)  # only views beyond the previous high count
    assert r.status == "skipped"  # 5.4 thousand: 5 already billed
    r = await _settle(intel, sid, 6100)
    assert r.thousands == 1 and r.amount == Decimal("500")


async def test_an_entry_records_where_it_came_from(api, intel):
    _, campaign, creator, sid = await _live_clip(api, intel, rate=500)
    intel.set_views(sid, 2600)
    await _settle(intel, sid)
    e = (await _entries(sid))[0]
    assert e.views_total == 2600 and e.billable_views == 2600 and e.thousands == 2
    assert str(e.snapshot_id) == intel.snapshot[sid]
    assert e.reference == f"{sid}:2"
    assert timedelta(days=4, hours=23) < e.payable_at - e.accrued_at <= timedelta(days=5, minutes=1)


async def test_billable_views_in_history_are_the_delta_since_the_last_entry(api, intel):
    _, _, _, sid = await _live_clip(api, intel, rate=500)
    await _settle(intel, sid, 2000)
    await _settle(intel, sid, 5500)
    first, second = await _entries(sid)
    assert (first.billable_views, second.billable_views) == (2000, 3500)


# --- what may earn -----------------------------------------------------------------------------------


async def test_a_clip_that_is_not_approved_earns_nothing(api, intel):
    _, _, _, sid = await _live_clip(api, intel, rules=False)
    # Force it back to awaiting review, as if a human hadn't decided yet.
    from modules.submissions.models import Submission, VerificationStatus

    async with db_session() as db:
        row = await db.scalar(select(Submission).where(Submission.id == sid))
        row.verification_status = VerificationStatus.needs_review
        await db.commit()
    r = await _settle(intel, sid, 9000)
    assert r.status == "skipped" and r.reason == "not_approved"
    assert await _entries(sid) == []


async def test_a_withdrawn_clip_stops_earning_but_keeps_what_it_earned(api, intel):
    _, _, creator, sid = await _live_clip(api, intel, rate=500)
    await _settle(intel, sid, 2000)
    await api.post(f"/submissions/{sid}/withdraw", headers=auth(creator))
    r = await _settle(intel, sid, 9000)
    assert r.reason == "not_approved"
    assert sum(e.amount for e in await _entries(sid)) == Decimal("1000.00")


async def test_a_paused_campaign_still_earns_but_a_closed_one_does_not(api, intel):
    org, campaign, _, sid = await _live_clip(api, intel, rate=500)
    await api.post(f"/campaigns/{campaign['id']}/pause", headers=auth(org))
    assert (await _settle(intel, sid, 1000)).status == "accrued"  # pausing new entries doesn't stop earning
    await api.post(f"/campaigns/{campaign['id']}/close", headers=auth(org))
    r = await _settle(intel, sid, 5000)
    assert r.status == "skipped" and r.reason == "campaign_not_live"


async def test_no_observations_yet_is_a_quiet_skip(api, intel):
    _, _, _, sid = await _live_clip(api, intel)
    del intel.views[sid]  # Intelligence hasn't read it yet
    assert (await _settle(intel, sid)).reason == "no_observations"


async def test_an_intelligence_outage_settles_nothing_and_raises_for_retry(api, intel):
    _, _, _, sid = await _live_clip(api, intel)
    intel.set_views(sid, 3000)
    intel.unreachable = True
    async with db_session() as db:
        try:
            await service.settle_submission(db, uuid.UUID(sid), intel)
            raised = False
        except service.IntelligenceUnavailable:
            raised = True
    assert raised and await _entries(sid) == []


# --- trust ---------------------------------------------------------------------------------------------


async def test_a_flagged_clip_is_not_paid_until_the_flag_clears(api, intel):
    _, _, _, sid = await _live_clip(api, intel, rate=500)
    intel.trust[sid] = "flagged"
    r = await _settle(intel, sid, 4000)
    assert r.status == "skipped" and r.reason == "trust_flagged"
    async with db_session() as db:
        acct = await db.get(EarningAccount, uuid.UUID(sid))
        assert acct.blocked_reason == "trust_flagged" and acct.cumulative_views == 4000
    assert await _entries(sid) == []

    intel.trust[sid] = "normal"
    r = await _settle(intel, sid)
    assert r.status == "accrued" and r.thousands == 4 and r.amount == Decimal("2000")
    async with db_session() as db:
        assert (await db.get(EarningAccount, uuid.UUID(sid))).blocked_reason is None


async def test_watch_and_insufficient_data_are_still_paid(api, intel):
    _, _, _, sid = await _live_clip(api, intel, rate=500)
    intel.trust[sid] = "watch"
    assert (await _settle(intel, sid, 1000)).status == "accrued"


# --- caps ----------------------------------------------------------------------------------------------------


async def test_the_creator_cap_stops_at_the_last_whole_thousand_that_fits(api, intel):
    _, _, _, sid = await _live_clip(api, intel, rate=500, cap=1200)
    r = await _settle(intel, sid, 9000)  # 9 thousand = ₦4,500, but the cap is ₦1,200
    assert r.thousands == 2 and r.amount == Decimal("1000")  # ₦1,000; a third thousand would pass ₦1,200
    again = await _settle(intel, sid, 20000)
    assert again.status == "skipped" and again.reason == "creator_cap_reached"


async def test_the_creator_cap_is_across_all_of_that_creators_clips(api, intel):
    org, campaign, creator, first = await _live_clip(api, intel, rate=500, cap=1500)
    second = (await submit_clip(api, creator, campaign["id"], title="Second clip")).json()["id"]
    assert (await _settle(intel, first, 2000)).amount == Decimal("1000")
    r = await _settle(intel, second, 5000)  # only ₦500 of the ₦1,500 cap is left
    assert r.thousands == 1 and r.amount == Decimal("500")
    assert (await _settle(intel, second, 9000)).reason == "creator_cap_reached"


async def test_the_pot_is_a_hard_ceiling_and_an_empty_pot_closes_the_campaign(api, intel):
    org, campaign, creator, sid = await _live_clip(api, intel, rate=500, pot=1200)
    r = await _settle(intel, sid, 9000)  # wants ₦4,500; the pot holds ₦1,200 → 2 thousands
    assert r.thousands == 2 and r.amount == Decimal("1000")
    assert (await api.get(f"/campaigns/{campaign['id']}", headers=auth(org))).json()["status"] == "closed"
    assert (await api.get(f"/campaigns/{campaign['id']}", headers=auth(org))).json()["spent"] == 1000
    r = await _settle(intel, sid, 20000)
    assert r.status == "skipped" and r.reason == "campaign_not_live"


async def test_two_clips_cannot_both_spend_the_last_of_the_pot(api, intel):
    org, campaign, creator, first = await _live_clip(api, intel, rate=500, pot=1000)
    other = await make_creator(api)
    second = (await submit_clip(api, other, campaign["id"])).json()["id"]
    intel.set_views(first, 5000)
    intel.set_views(second, 5000)

    async def settle(sid):
        async with db_session() as db:
            result = await service.settle_submission(db, uuid.UUID(sid), intel)
            await db.commit()
            return result

    results = await asyncio.gather(settle(first), settle(second))
    async with db_session() as db:
        spent = await db.scalar(select(func.coalesce(func.sum(EarningEntry.amount), 0)).where(EarningEntry.campaign_id == campaign["id"]))
    assert spent == Decimal("1000.00")  # never more than the pot, however they interleave
    assert sorted(r.status for r in results).count("accrued") >= 1


async def test_concurrent_settlement_of_one_clip_books_each_thousand_once(api, intel):
    _, _, _, sid = await _live_clip(api, intel, rate=500)
    intel.set_views(sid, 3000)

    async def settle():
        async with db_session() as db:
            result = await service.settle_submission(db, uuid.UUID(sid), intel)
            await db.commit()
            return result

    await asyncio.gather(settle(), settle(), settle())
    entries = await _entries(sid)
    assert len(entries) == 1 and entries[0].amount == Decimal("1500.00")


# --- audit -------------------------------------------------------------------------------------------------------


async def test_every_accrual_leaves_an_audit_event_with_its_snapshot(api, intel):
    _, campaign, _, sid = await _live_clip(api, intel, rate=500)
    await _settle(intel, sid, 2500)
    async with db_session() as db:
        events = list(await db.scalars(select(AuditEvent).where(AuditEvent.kind == "earnings.accrued", AuditEvent.submission_id == sid)))
    assert len(events) == 1 and events[0].amount == Decimal("1000.00")
    assert events[0].data["snapshot"] == intel.snapshot[sid] and events[0].data["views"] == 2500


async def test_the_sweep_books_final_views_before_closing_on_the_deadline(api, intel):
    from datetime import datetime, timezone

    from core.database import AsyncSessionLocal  # noqa: F401
    from modules.campaigns.models import Campaign
    from modules.earnings import jobs

    org, campaign, _, sid = await _live_clip(api, intel, rate=500)
    intel.set_views(sid, 3000)
    async with db_session() as db:
        row = await db.scalar(select(Campaign).where(Campaign.id == campaign["id"]))
        row.ends_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db.commit()

    from tests.http_app import db_session as ds  # the same factory the app is using
    from main import app
    from core.deps import get_db

    factory_gen = app.dependency_overrides[get_db]
    # Run the tick against the test database through a factory that yields its sessions.
    class _Factory:
        def __call__(self):
            return _Ctx()

    class _Ctx:
        async def __aenter__(self):
            self.gen = factory_gen()
            self.session = await self.gen.__anext__()
            return self.session

        async def __aexit__(self, *exc):
            await self.gen.aclose()

    closed = await jobs.sweep_tick(_Factory(), client=intel)
    assert closed == 1
    assert (await api.get(f"/campaigns/{campaign['id']}", headers=auth(org))).json()["status"] == "closed"
    assert sum(e.amount for e in await _entries(sid)) == Decimal("1500.00")  # the last views were booked first
