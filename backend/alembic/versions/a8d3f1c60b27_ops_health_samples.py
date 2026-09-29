"""ops health samples (30-day availability)

Revision ID: a8d3f1c60b27
Revises: e4c7a9b2d6f1
Create Date: 2026-09-29 12:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8d3f1c60b27"
down_revision: Union[str, None] = "e4c7a9b2d6f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if "ops_health_samples" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "ops_health_samples",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("service", sa.String(length=32), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ops_health_service_ts", "ops_health_samples", ["service", "ts"])


def downgrade() -> None:
    op.drop_index("ix_ops_health_service_ts", table_name="ops_health_samples")
    op.drop_table("ops_health_samples")
