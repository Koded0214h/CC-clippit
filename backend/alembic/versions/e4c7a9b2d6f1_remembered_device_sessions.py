"""remembered device sessions

Revision ID: e4c7a9b2d6f1
Revises: d2e7f4a9c1b3
Create Date: 2026-09-28 22:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4c7a9b2d6f1"
down_revision: Union[str, None] = "d2e7f4a9c1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE auth_code_purpose ADD VALUE IF NOT EXISTS 'remember_device'")

    columns = {column["name"] for column in sa.inspect(bind).get_columns("sessions")}
    if "remembered_at" not in columns:
        op.add_column("sessions", sa.Column("remembered_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("sessions")}
    if "remembered_at" in columns:
        op.drop_column("sessions", "remembered_at")
    # PostgreSQL enum values are intentionally retained. Removing one safely
    # requires rebuilding the type and risks existing auth-code rows.
