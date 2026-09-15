"""intelligence: content_tracking (polling state)

The poller's queue. `(status, next_poll_at)` is the only index it needs —
"what's due" is a range scan over active rows, which is why this doesn't
require a separate queue system to operate.

Revision ID: c93a7f20d118
Revises: b7c41e05a9d2
Create Date: 2026-09-14 10:05:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c93a7f20d118'
down_revision: Union[str, None] = 'b7c41e05a9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'content_tracking',
        sa.Column('content_id', sa.Uuid(), nullable=False),
        sa.Column(
            'status',
            # VARCHAR + CHECK, same reasoning as the previous migration.
            sa.Enum(
                'active', 'stopped', 'dead_lettered',
                name='content_tracking_status', native_enum=False,
                create_constraint=True, length=32,
            ),
            nullable=False,
        ),
        sa.Column('next_poll_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_polled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False),
        sa.Column('last_error_code', sa.String(length=64), nullable=True),
        sa.Column('last_error_message', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['content_id'], ['social_content.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('content_id'),
    )
    op.create_index('ix_content_tracking_due', 'content_tracking', ['status', 'next_poll_at'])


def downgrade() -> None:
    op.drop_index('ix_content_tracking_due', table_name='content_tracking')
    op.drop_table('content_tracking')
