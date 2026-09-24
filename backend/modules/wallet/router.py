"""PRD V1's wallet surface. `GET /wallet` answers for either role — see
`schemas.BrandWalletOut`/`CreatorWalletOut` — so the frontend has one
contract instead of branching on `/earnings/summary` vs. something new.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.deps import get_db
from core.money import to_decimal, quantize
from core.rate_limit import limiter
from integrations.payments import get_provider
from integrations.payments.base import AccountNotFound, ProviderError
from modules.auth.deps import get_current_user
from modules.auth.models import Role, User
from modules.campaigns.service import now
from modules.earnings import queries as earnings_queries
from modules.organisations.models import OrganisationBankAccount

from . import models, schemas, service

router = APIRouter(tags=["wallet"])


def _require_organisation(user: User) -> None:
    if user.role != Role.organisation:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an organisation account has a brand wallet")


# --- brand bank details (mirrors modules.creators.router's creator ones) -------


@router.put("/organisations/me/bank-details", response_model=schemas.OrgBankAccountOut)
async def set_org_bank_details(
    payload: schemas.OrgBankAccountIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    _require_organisation(user)
    account = await db.get(OrganisationBankAccount, user.id)
    if account:
        account.bank_code = payload.bank_code
        account.bank_name = payload.bank_name
        account.account_number = payload.account_number
        account.account_name = None
        account.verified = False
        account.verified_at = None
    else:
        account = OrganisationBankAccount(organisation_id=user.id, **payload.model_dump())
        db.add(account)
    await db.commit()
    await db.refresh(account)
    return schemas.OrgBankAccountOut.from_model(account)


@router.get("/organisations/me/bank-details", response_model=schemas.OrgBankAccountOut)
async def get_org_bank_details(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _require_organisation(user)
    account = await db.get(OrganisationBankAccount, user.id)
    if not account:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bank details on file yet")
    return schemas.OrgBankAccountOut.from_model(account)


@router.post("/organisations/me/bank-details/verify", response_model=schemas.OrgBankAccountOut)
@limiter.limit("10/minute")
async def verify_org_bank_details(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    _require_organisation(user)
    account = await db.get(OrganisationBankAccount, user.id)
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
    return schemas.OrgBankAccountOut.from_model(account)


# --- the wallet read --------------------------------------------------------------


@router.get("/wallet")
async def get_wallet(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    if user.role == Role.organisation:
        balance = await service.brand_balance(db, user.id)
        return schemas.BrandWalletOut(
            available=balance.available, reserved=balance.reserved, withdrawn_all_time=balance.withdrawn,
            min_withdrawal=settings.min_withdrawal, withdrawal_fee_rate=settings.withdrawal_fee_rate,
        )
    if user.role == Role.creator:
        b = await earnings_queries.balances(db, user.id)
        return schemas.CreatorWalletOut(
            held=b.in_hold, available=b.payable, processing=b.processing, paid_all_time=b.paid,
            min_withdrawal=settings.min_withdrawal, withdrawal_fee_rate=settings.withdrawal_fee_rate,
        )
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin accounts don't have a wallet")


# --- brand withdrawals ---------------------------------------------------------


def _fail(exc: service.WalletError) -> HTTPException:
    return HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.message})


def _out(withdrawal: models.OrganisationWithdrawal) -> schemas.WithdrawalOut:
    provider = get_provider()
    return schemas.WithdrawalOut(
        id=withdrawal.id, reference=withdrawal.reference, status=withdrawal.status, amount=withdrawal.amount,
        fee=withdrawal.fee, net=withdrawal.amount - withdrawal.fee, organisation_name=withdrawal.account_name,
        destination=schemas.WithdrawalDestination(
            bank_code=withdrawal.bank_code, bank_name=withdrawal.bank_name,
            account_number_masked=service.mask(withdrawal.account_number), account_name=withdrawal.account_name,
        ),
        provider=withdrawal.provider, sandbox=provider.sandbox, failure_reason=withdrawal.failure_reason,
        initiated_at=withdrawal.initiated_at, completed_at=withdrawal.completed_at,
    )


@router.post("/wallet/withdraw/quote", response_model=schemas.WithdrawalQuoteOut)
@limiter.limit("30/minute")
async def quote_withdrawal(request: Request, payload: schemas.WithdrawalCreate, user: User = Depends(get_current_user)):
    _require_organisation(user)
    settings = get_settings()
    amount = quantize(to_decimal(payload.amount))
    if amount < settings.min_withdrawal:
        raise HTTPException(422, f"The minimum withdrawal is ₦{settings.min_withdrawal:,}.")
    fee = quantize(amount * to_decimal(settings.withdrawal_fee_rate))
    return schemas.WithdrawalQuoteOut(amount=amount, fee=fee, net_amount=amount - fee)


@router.post("/wallet/withdraw", response_model=schemas.WithdrawalOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def withdraw(
    request: Request, payload: schemas.WithdrawalCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    _require_organisation(user)
    try:
        withdrawal, created = await service.reserve(db, user, to_decimal(payload.amount), payload.idempotency_key)
    except service.WalletError as exc:
        await db.rollback()
        raise _fail(exc) from exc
    await db.commit()

    if created:
        await service.dispatch(db, withdrawal.id)
        await db.commit()
        await db.refresh(withdrawal)
    return _out(withdrawal)


@router.get("/wallet/withdrawals", response_model=list[schemas.WithdrawalOut])
async def list_withdrawals(
    limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    _require_organisation(user)
    rows = await db.scalars(
        select(models.OrganisationWithdrawal).where(models.OrganisationWithdrawal.organisation_id == user.id)
        .order_by(models.OrganisationWithdrawal.initiated_at.desc()).limit(limit).offset(offset)
    )
    return [_out(w) for w in rows]


@router.get("/wallet/withdrawals/{withdrawal_id}", response_model=schemas.WithdrawalOut)
async def read_withdrawal(withdrawal_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    withdrawal = await db.get(models.OrganisationWithdrawal, withdrawal_id)
    if withdrawal is None or (user.role != Role.admin and withdrawal.organisation_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Withdrawal not found")
    return _out(withdrawal)
