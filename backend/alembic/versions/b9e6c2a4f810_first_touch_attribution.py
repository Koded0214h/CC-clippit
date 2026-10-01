"""make creator attribution first-touch only

Revision ID: b9e6c2a4f810
Revises: a8d3f1c60b27
Create Date: 2026-09-30 20:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9e6c2a4f810"
down_revision: Union[str, None] = "a8d3f1c60b27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE campaigns SET attribution_model = 'first_touch'")
    op.alter_column(
        "campaigns",
        "attribution_model",
        existing_type=sa.String(length=20),
        server_default="first_touch",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "campaigns",
        "attribution_model",
        existing_type=sa.String(length=20),
        server_default="last_touch",
        existing_nullable=False,
    )
