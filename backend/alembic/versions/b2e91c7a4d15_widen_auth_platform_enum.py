"""Widen auth's `platform` enum to match core.platforms.Platform.

Until this lands, `/internal/social-accounts/{id}/x/token` 422s because
the path param is typed as a four-value enum. Intelligence already stores
six values on `social_content`; auth catching up is decision D5.

Revision ID: b2e91c7a4d15
Revises: a1c8e4d2b6f0
Create Date: 2026-09-19 19:20:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b2e91c7a4d15"
down_revision: Union[str, None] = "a1c8e4d2b6f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres 12+ allows ADD VALUE inside a transaction; the new labels
    # just cannot be *used* until the transaction commits, which is fine
    # because this migration only adds them.
    op.execute("ALTER TYPE platform ADD VALUE IF NOT EXISTS 'x'")
    op.execute("ALTER TYPE platform ADD VALUE IF NOT EXISTS 'youtube'")


def downgrade() -> None:
    # Native enum values cannot be dropped without rewriting the type.
    # Leave them; unused labels are harmless.
    pass
