import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditEvent


def record(
    db: AsyncSession,
    kind: str,
    *,
    actor_id: uuid.UUID | None = None,
    campaign_id: uuid.UUID | None = None,
    submission_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    amount: Decimal | None = None,
    **data,
) -> AuditEvent:
    """Adds an event to the caller's session, so it commits — or rolls back —
    together with the change it describes. `data` must be JSON-serialisable."""
    event = AuditEvent(
        kind=kind,
        actor_id=actor_id,
        campaign_id=campaign_id,
        submission_id=submission_id,
        subject_id=subject_id,
        amount=amount,
        data={k: (str(v) if isinstance(v, (Decimal, uuid.UUID)) else v) for k, v in data.items()},
    )
    db.add(event)
    return event
