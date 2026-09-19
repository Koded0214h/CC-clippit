"""intelligence: trust evaluations and reviews

Two tables with opposite characters. `trust_evaluations` is the machine's
opinion — rewritten if the same observation is re-judged under new rules.
`trust_reviews` is a human's conclusion, append-only, because a reviewer
changing their mind is a second review and someone will eventually need
to know what was believed at the moment a payout was released.

`signals` is JSON rather than a child table on purpose: the signal set
changes with every tuning pass, and each stored signal keeps the
threshold it was compared against so old decisions stay readable after
the thresholds move.

Revision ID: f47c16b8e920
Revises: 9641c7e569bf
Create Date: 2026-09-19 10:45:00.000000

Chained after the campaigns/submissions/creators migrations rather than
after `e5b2d9143a70` (the last intelligence one), which would have left
two heads and broken `alembic upgrade head` for everybody. These tables
only depend on `social_content` and `metric_snapshots`, which are
ancestors on either path, so the ordering is free.

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = 'f47c16b8e920'
down_revision: Union[str, None] = '9641c7e569bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RAW_JSON = sa.JSON().with_variant(JSONB, "postgresql")


def _checked_enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=32)


def upgrade() -> None:
    op.create_table(
        'trust_evaluations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('content_id', sa.Uuid(), nullable=False),
        sa.Column('snapshot_id', sa.Uuid(), nullable=False),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            'status',
            _checked_enum(
                'normal', 'watch', 'flagged', 'insufficient_data',
                name='trust_evaluation_status',
            ),
            nullable=False,
        ),
        sa.Column('anomaly_score', sa.Float(), nullable=False),
        sa.Column('signals', RAW_JSON, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['content_id'], ['social_content.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['snapshot_id'], ['metric_snapshots.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('snapshot_id', name='uq_trust_evaluation_snapshot'),
    )
    op.create_index(
        'ix_trust_evaluations_content_evaluated', 'trust_evaluations', ['content_id', 'evaluated_at']
    )
    # The admin queue: worst score first within a status.
    op.create_index('ix_trust_evaluations_status', 'trust_evaluations', ['status', 'anomaly_score'])

    op.create_table(
        'trust_reviews',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('content_id', sa.Uuid(), nullable=False),
        sa.Column('evaluation_id', sa.Uuid(), nullable=True),
        sa.Column(
            'outcome',
            _checked_enum('legitimate', 'fraudulent', 'inconclusive', name='trust_review_outcome'),
            nullable=False,
        ),
        sa.Column(
            'source',
            _checked_enum('flagged_queue', 'random_audit', 'dispute', name='trust_review_source'),
            nullable=False,
        ),
        sa.Column('reviewer_id', sa.Uuid(), nullable=False),
        sa.Column('notes', sa.String(length=2000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['content_id'], ['social_content.id'], ondelete='CASCADE'),
        # SET NULL rather than CASCADE: losing an evaluation must not
        # delete the human label that was attached to it.
        sa.ForeignKeyConstraint(['evaluation_id'], ['trust_evaluations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_trust_reviews_content', 'trust_reviews', ['content_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_trust_reviews_content', table_name='trust_reviews')
    op.drop_table('trust_reviews')
    op.drop_index('ix_trust_evaluations_status', table_name='trust_evaluations')
    op.drop_index('ix_trust_evaluations_content_evaluated', table_name='trust_evaluations')
    op.drop_table('trust_evaluations')
