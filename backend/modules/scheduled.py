"""Registers the periodic jobs. Imported once by main.py; nothing runs until
`BACKGROUND_JOBS_ENABLED` is set (see core.jobs). Intervals are first guesses
— settlement cadence in particular should follow Intelligence's polling tiers
(decision D16), which are also untuned."""

from core.config import get_settings
from core.jobs import register
from modules.earnings import jobs as earnings_jobs
from modules.payouts import jobs as payout_jobs
from modules.wallet import jobs as wallet_jobs


async def _settle() -> None:
    await earnings_jobs.settle_tick()


async def _sweep() -> None:
    await earnings_jobs.sweep_tick()


async def _payable() -> None:
    await earnings_jobs.notify_payable_tick()


async def _reconcile() -> None:
    await payout_jobs.reconcile_tick()


async def _wallet_reconcile() -> None:
    await wallet_jobs.reconcile_tick()


async def _intelligence_poll() -> None:
    """One Intelligence tick inside the API process when background jobs
    are enabled. The dedicated `python -m modules.intelligence.worker`
    process remains the preferred production path; this is the same
    `run_due()` body so either runtime is enough for Stage 3."""
    from modules.intelligence.worker import build_coordinator

    await build_coordinator().run_due()


register("earnings.settle", 300, _settle)
register("campaigns.sweep", 300, _sweep)
register("earnings.notify_payable", 900, _payable)
register("payouts.reconcile", 120, _reconcile)
register("wallet.reconcile", 120, _wallet_reconcile)
register(
    "intelligence.poll",
    max(get_settings().intelligence_poll_tick_seconds, 30),
    _intelligence_poll,
)
