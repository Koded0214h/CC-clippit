"""onboarding: store every answer the onboarding screens ask

Revision ID: a3d9f1c7e2b4
Revises: e7ee85ab6841
Create Date: 2026-09-25 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a3d9f1c7e2b4'
down_revision: Union[str, None] = 'e7ee85ab6841'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('creator_profiles', sa.Column('location', sa.String(length=80), nullable=True))
    op.add_column(
        'creator_profiles',
        sa.Column('viewing_interests', postgresql.ARRAY(sa.String(length=40)), nullable=False, server_default='{}'),
    )

    op.add_column('organisation_profiles', sa.Column('contact_name', sa.String(length=80), nullable=True))
    op.add_column('organisation_profiles', sa.Column('location', sa.String(length=80), nullable=True))
    op.add_column('organisation_profiles', sa.Column('funder_type', sa.String(length=20), nullable=True))
    op.add_column('organisation_profiles', sa.Column('registered', sa.Boolean(), nullable=True))
    op.add_column(
        'organisation_profiles',
        sa.Column('content_interests', postgresql.ARRAY(sa.String(length=40)), nullable=False, server_default='{}'),
    )
    op.add_column(
        'organisation_profiles',
        sa.Column('viewing_interests', postgresql.ARRAY(sa.String(length=40)), nullable=False, server_default='{}'),
    )
    op.add_column('organisation_profiles', sa.Column('discovery_source', sa.String(length=60), nullable=True))


def downgrade() -> None:
    for column in ('discovery_source', 'viewing_interests', 'content_interests', 'registered', 'funder_type', 'location', 'contact_name'):
        op.drop_column('organisation_profiles', column)
    op.drop_column('creator_profiles', 'viewing_interests')
    op.drop_column('creator_profiles', 'location')
