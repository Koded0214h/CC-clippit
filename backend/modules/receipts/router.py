"""Public receipt verification — anyone with a reference (a creator
sharing a payout receipt, a brand's finance team checking a funding
certificate) can confirm it's real, without signing in and without
seeing anything private. See core.receipts for the digest and
production-api-inventory.md §J for what's still missing (the PDFs
themselves)."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from core.rate_limit import limiter
from core.receipts import digest as make_digest
from modules.funding.models import FundingOrder
from modules.payouts.models import Payout
from modules.refunds.models import Refund

from . import schemas

router = APIRouter(tags=["receipts"])


@router.get("/receipts/{reference}/verify", response_model=schemas.ReceiptVerifyOut)
@limiter.limit("30/minute")
async def verify_receipt(request: Request, reference: str, db: AsyncSession = Depends(get_db)):
    order = await db.scalar(select(FundingOrder).where(FundingOrder.reference == reference))
    if order is not None:
        return schemas.ReceiptVerifyOut(
            reference=reference, type="funding", amount=order.total_amount, status=order.status.value,
            date=order.confirmed_at or order.created_at,
            digest=make_digest(reference, order.total_amount, order.status.value, order.confirmed_at or order.created_at),
        )

    payout = await db.scalar(select(Payout).where(Payout.reference == reference))
    if payout is not None:
        at = payout.completed_at or payout.initiated_at
        return schemas.ReceiptVerifyOut(
            reference=reference, type="payout", amount=payout.amount, status=payout.status.value, date=at,
            digest=make_digest(reference, payout.amount, payout.status.value, at),
        )

    refund = await db.scalar(select(Refund).where(Refund.reference == reference))
    if refund is not None:
        at = refund.processed_at or refund.created_at
        return schemas.ReceiptVerifyOut(
            reference=reference, type="refund", amount=refund.amount, status=refund.status.value, date=at,
            digest=make_digest(reference, refund.amount, refund.status.value, at),
        )

    raise HTTPException(status.HTTP_404_NOT_FOUND, "No receipt found for that reference")
