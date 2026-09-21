import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from core.money import to_decimal
from core.rate_limit import limiter
from integrations.payments import get_provider
from integrations.payments.base import AccountNotFound, ProviderError
from modules.auth.deps import get_current_user, get_verified_user
from modules.auth.models import Role, User
from modules.campaigns.service import now
from modules.creators import schemas as creator_schemas
from modules.creators.models import CreatorBankAccount

from . import models, schemas, service

router = APIRouter(tags=["payouts"])


def _creator(user: User) -> None:
    if user.role != Role.creator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a creator account can withdraw")


def _fail(exc: service.PayoutError) -> HTTPException:
    return HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.message})


# --- bank account verification ---------------------------------------------------------


@router.post("/banks/resolve", response_model=schemas.ResolvedOut)
@limiter.limit("15/minute")
async def resolve_account(request: Request, payload: schemas.ResolveRequest, user: User = Depends(get_current_user)):
    """Look an account up *before* saving it, so the creator can check the
    name is theirs."""
    try:
        resolved = await get_provider().resolve_account(account_number=payload.account_number, bank_code=payload.bank_code)
    except AccountNotFound as exc:
        raise HTTPException(422, str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "We couldn't check that account right now. Try again shortly.") from exc
    return schemas.ResolvedOut(
        account_name=resolved.account_name, bank_code=resolved.bank_code,
        account_number_masked=service.mask(resolved.account_number),
    )


@router.post("/creators/me/bank-details/verify", response_model=creator_schemas.BankAccountOut)
@limiter.limit("10/minute")
async def verify_bank_details(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Checks the saved account with the payment provider and stores the name
    it belongs to. Required before a first withdrawal."""
    _creator(user)
    account = await db.get(CreatorBankAccount, user.id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Add your bank details first.")
    try:
        resolved = await get_provider().resolve_account(account_number=account.account_number, bank_code=account.bank_code)
    except AccountNotFound as exc:
        raise HTTPException(422, str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "We couldn't check that account right now. Try again shortly.") from exc

    account.account_name = resolved.account_name
    account.verified = True
    account.verified_at = now()
    await db.commit()
    await db.refresh(account)
    return creator_schemas.BankAccountOut.from_model(account)


# --- withdrawals ----------------------------------------------------------------------------


@router.post("/payouts", response_model=schemas.PayoutOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def withdraw(
    request: Request,
    payload: schemas.PayoutCreate,
    user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Withdraw payable earnings to the verified bank account. Reserves the
    money first, then sends — see `service` for why that order matters."""
    _creator(user)
    try:
        payout, created = await service.reserve(db, user, to_decimal(payload.amount), payload.idempotency_key)
    except service.PayoutError as exc:
        await db.rollback()
        raise _fail(exc) from exc
    await db.commit()

    if created:
        await service.dispatch(db, payout.id)
        await db.commit()
        await db.refresh(payout)
    return (await service.present(db, [payout], with_provenance=True))[0]


@router.get("/payouts", response_model=schemas.PayoutList)
async def list_payouts(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _creator(user)
    total = await db.scalar(select(func.count()).select_from(models.Payout).where(models.Payout.creator_id == user.id))
    rows = list(
        await db.scalars(
            select(models.Payout).where(models.Payout.creator_id == user.id)
            .order_by(models.Payout.initiated_at.desc()).limit(limit).offset(offset)
        )
    )
    return schemas.PayoutList(items=await service.present(db, rows, with_provenance=False), total=int(total or 0))


@router.get("/payouts/{payout_id}", response_model=schemas.PayoutOut)
async def read_payout(payout_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """The receipt. A payout is visible to its creator and to admin only."""
    payout = await db.get(models.Payout, payout_id)
    if payout is None or (user.role != Role.admin and payout.creator_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payout not found")
    return (await service.present(db, [payout], with_provenance=True))[0]
