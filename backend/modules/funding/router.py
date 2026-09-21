from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from integrations.payments import get_provider
from modules.auth.deps import get_verified_user
from modules.auth.models import User
from modules.campaigns import service as campaign_service

from . import schemas, service

router = APIRouter(prefix="/campaigns", tags=["funding"])


async def _owned(ref: str, user: User, db: AsyncSession):
    campaign = await campaign_service.resolve(db, ref)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    campaign_service.ensure_can_manage(campaign, user)
    return campaign


def _fail(exc: service.FundingError) -> HTTPException:
    return HTTPException(exc.status_code, exc.message)


@router.post("/{campaign_ref}/funding", response_model=schemas.FundingOrderOut, status_code=status.HTTP_201_CREATED)
async def start_funding(
    campaign_ref: str,
    payload: schemas.FundingCreate,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Creates the funding order (or returns the open one — safe to call
    twice). From here the campaign's terms are locked."""
    campaign = await _owned(campaign_ref, user, db)
    try:
        order = await service.create_order(db, campaign, user, payload.method)
    except service.FundingError as exc:
        raise _fail(exc) from exc
    await db.commit()
    await db.refresh(campaign)
    return service.order_out(order, campaign, get_provider())


@router.get("/{campaign_ref}/funding", response_model=schemas.FundingOrderOut)
async def read_funding(campaign_ref: str, user: User = Depends(get_verified_user), db: AsyncSession = Depends(get_db)):
    campaign = await _owned(campaign_ref, user, db)
    order = await service.latest_order(db, campaign.id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This campaign has no funding order yet.")
    return service.order_out(order, campaign, get_provider())


@router.post("/{campaign_ref}/funding/confirm", response_model=schemas.FundingOrderOut)
async def confirm_funding(campaign_ref: str, user: User = Depends(get_verified_user), db: AsyncSession = Depends(get_db)):
    """"I have funded the pot." Asks the provider whether the money arrived:
    if it did the campaign opens; if not, the order waits (`awaiting_confirmation`)
    for the provider's webhook. The brand's claim alone never opens a campaign."""
    campaign = await _owned(campaign_ref, user, db)
    order = await service.latest_order(db, campaign.id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This campaign has no funding order yet.")
    try:
        order = await service.confirm_with_provider(db, order, campaign, user)
    except service.FundingError as exc:
        raise _fail(exc) from exc
    await db.commit()
    await db.refresh(campaign)
    return service.order_out(order, campaign, get_provider())


@router.delete("/{campaign_ref}/funding", response_model=schemas.FundingOrderOut)
async def cancel_funding(campaign_ref: str, user: User = Depends(get_verified_user), db: AsyncSession = Depends(get_db)):
    """Cancels an unpaid order and returns the campaign to draft so its terms
    can be edited. Refused once the brand says they've paid."""
    campaign = await _owned(campaign_ref, user, db)
    try:
        order = await service.cancel_order(db, campaign, user)
    except service.FundingError as exc:
        raise _fail(exc) from exc
    await db.commit()
    await db.refresh(campaign)
    return service.order_out(order, campaign, get_provider())
