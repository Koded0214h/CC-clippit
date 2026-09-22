import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_db
from modules.auth.deps import get_current_user
from modules.auth.models import User

from . import documents, models, schemas

router = APIRouter(tags=["legal"])


@router.get("/legal/documents/{slug}", response_model=schemas.LegalDocumentOut)
async def get_document(slug: str):
    doc = documents.get(slug)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such document")
    return schemas.LegalDocumentOut(
        slug=doc.slug, version=doc.version, title=doc.title, effective_date=doc.effective_date, body=doc.body
    )


def _hash_ip(request: Request) -> str | None:
    ip = request.client.host if request.client else None
    return hashlib.sha256(ip.encode()).hexdigest() if ip else None


@router.post("/legal/acceptances", response_model=schemas.AcceptanceOut, status_code=status.HTTP_201_CREATED)
async def accept_document(
    request: Request,
    payload: schemas.AcceptanceIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = documents.get(payload.slug)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such document")
    if payload.version != doc.version:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{payload.slug} is now at version {doc.version}.")

    existing = await db.scalar(
        select(models.LegalAcceptance).where(
            models.LegalAcceptance.user_id == user.id,
            models.LegalAcceptance.slug == payload.slug,
            models.LegalAcceptance.version == payload.version,
        )
    )
    if existing is None:
        existing = models.LegalAcceptance(
            user_id=user.id, slug=payload.slug, version=payload.version, action=payload.action, ip_hash=_hash_ip(request)
        )
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
    return schemas.AcceptanceOut(
        slug=existing.slug, version=existing.version, action=existing.action, accepted_at=existing.accepted_at
    )


@router.get("/legal/acceptances/me", response_model=schemas.MyAcceptancesOut)
async def my_acceptances(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(select(models.LegalAcceptance).where(models.LegalAcceptance.user_id == user.id)))
    accepted_current = {r.slug for r in rows if r.version == documents.current_versions().get(r.slug)}
    newly_required = [slug for slug in documents.current_versions() if slug not in accepted_current]
    return schemas.MyAcceptancesOut(
        accepted=[
            schemas.AcceptanceOut(slug=r.slug, version=r.version, action=r.action, accepted_at=r.accepted_at)
            for r in rows
        ],
        newly_required=newly_required,
    )
