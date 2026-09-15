"""intelligence: content_features (derived, recomputable)

Deliberately disposable: every row here can be rebuilt from
`metric_snapshots` by `FeatureService.recompute_all`, which is the whole
reason observations and derived values live in separate tables.

`snapshot_id` is unique so recomputation is an upsert rather than a
duplicate, and `ON DELETE CASCADE` runs from both parents — a deleted
snapshot must not leave a feature row describing it behind.

Revision ID: e5b2d9143a70
Revises: c93a7f20d118
Create Date: 2026-09-14 10:35:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5b2d9143a70'
down_revision: Union[str, None] = 'c93a7f20d118'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'content_features',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('content_id', sa.Uuid(), nullable=False),
        sa.Column('snapshot_id', sa.Uuid(), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('incremental_views', sa.BigInteger(), nullable=True),
        sa.Column('view_velocity_per_hour', sa.Float(), nullable=True),
        sa.Column('growth_rate', sa.Float(), nullable=True),
        sa.Column('like_view_ratio', sa.Float(), nullable=True),
        sa.Column('comment_view_ratio', sa.Float(), nullable=True),
        sa.Column('share_view_ratio', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['content_id'], ['social_content.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['snapshot_id'], ['metric_snapshots.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('snapshot_id', name='uq_content_feature_snapshot'),
    )
    op.create_index(
        'ix_content_features_content_computed', 'content_features', ['content_id', 'computed_at']
    )


def downgrade() -> None:
    op.drop_index('ix_content_features_content_computed', table_name='content_features')
    op.drop_table('content_features')
