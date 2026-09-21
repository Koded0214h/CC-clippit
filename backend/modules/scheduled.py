"""Registers the periodic jobs. Imported once by main.py; nothing runs until
`BACKGROUND_JOBS_ENABLED` is set (see core.jobs). Intervals are first guesses
— settlement cadence in particular should follow Intelligence's polling tiers
(decision D16), which are also untuned."""

from core.jobs import register
from modules.earnings import jobs as earnings_jobs
from modules.payouts import jobs as payout_jobs


async def _settle() -> None:
    await earnings_jobs.settle_tick()


async def _sweep() -> None:
    await earnings_jobs.sweep_tick()


async def _payable() -> None:
    await earnings_jobs.notify_payable_tick()


async def _reconcile() -> None:
    await payout_jobs.reconcile_tick()


register("earnings.settle", 300, _settle)
register("campaigns.sweep", 300, _sweep)
register("earnings.notify_payable", 900, _payable)
register("payouts.reconcile", 120, _reconcile)
