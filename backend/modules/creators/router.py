import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from modules.auth.deps import get_current_user
from modules.auth.models import Role, User

from . import models, schemas

router = APIRouter(prefix="/creators", tags=["creators"])


@router.put("/me/bank-details", response_model=schemas.BankAccountOut)
async def set_bank_details(
    payload: schemas.BankAccountIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != Role.creator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a creator account has bank details")

    account = await db.get(models.CreatorBankAccount, user.id)
    if account:
        # Changing where money goes always re-requires verification — see
        # the model docstring. Setting the same details again also resets
        # it, deliberately: there's no way to tell "resubmitted unchanged"
        # from "changed back" from here, so the safer one always wins.
        account.bank_code = payload.bank_code
        account.bank_name = payload.bank_name
        account.account_number = payload.account_number
        account.account_name = None
        account.verified = False
        account.verified_at = None
    else:
        account = models.CreatorBankAccount(creator_id=user.id, **payload.model_dump())
        db.add(account)

    await db.commit()
    await db.refresh(account)
    return schemas.BankAccountOut.from_model(account)


@router.get("/me/bank-details", response_model=schemas.BankAccountOut)
async def get_my_bank_details(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != Role.creator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a creator account has bank details")

    account = await db.get(models.CreatorBankAccount, user.id)
    if not account:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bank details on file yet")
    return schemas.BankAccountOut.from_model(account)


@router.get("/{creator_id}/bank-details", response_model=schemas.BankAccountOut)
async def get_bank_details_for_admin(
    creator_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Support/dispute access only — an event manager has no business case
    to see a creator's bank details, so this is admin-only rather than
    following campaigns'/submissions' owner-or-admin pattern."""
    if user.role != Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")

    account = await db.get(models.CreatorBankAccount, creator_id)
    if not account:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bank details on file for this creator")
    return schemas.BankAccountOut.from_model(account)
