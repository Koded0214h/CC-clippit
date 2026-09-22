from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from integrations.payments import get_provider
from modules.auth.deps import get_current_user
from modules.auth.models import Role, User
from modules.campaigns import service as campaign_service

from . import models, schemas, service

router = APIRouter(tags=["refunds"])


def _out(refund: models.Refund) -> schemas.RefundOut:
    provider = get_provider()
    return schemas.RefundOut(
        id=refund.id, campaign_id=refund.campaign_id, amount=refund.amount, status=refund.status.value,
        reason=refund.reason, provider=refund.provider, sandbox=provider.sandbox,
        provider_reference=refund.provider_reference, failure_reason=refund.failure_reason,
        created_at=refund.created_at, processed_at=refund.processed_at,
    )


@router.post("/campaigns/{campaign_ref}/refunds", response_model=schemas.RefundOut, status_code=status.HTTP_201_CREATED)
async def request_refund(
    campaign_ref: str,
    payload: schemas.RefundIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    campaign = await campaign_service.resolve(db, campaign_ref)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    campaign_service.ensure_can_manage(campaign, user)
    try:
        refund = await service.create_refund(db, campaign, user, reason=payload.reason)
    except service.RefundError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    await db.commit()
    return _out(refund)


@router.get("/campaigns/{campaign_ref}/refunds", response_model=list[schemas.RefundOut])
async def list_refunds(campaign_ref: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    campaign = await campaign_service.resolve(db, campaign_ref)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    campaign_service.ensure_can_manage(campaign, user)
    rows = await db.scalars(
        select(models.Refund).where(models.Refund.campaign_id == campaign.id).order_by(models.Refund.created_at.desc())
    )
    return [_out(r) for r in rows]
