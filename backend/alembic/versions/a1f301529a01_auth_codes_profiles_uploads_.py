"""auth codes, profiles, uploads, notifications

Revision ID: a1f301529a01
Revises: b2e91c7a4d15
Create Date: 2026-09-21 08:30:48.251057

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1f301529a01'
down_revision: Union[str, None] = 'b2e91c7a4d15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('auth_codes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('purpose', sa.Enum('email_verify', 'password_reset', name='auth_code_purpose'), nullable=False),
    sa.Column('code_hash', sa.String(length=64), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'purpose', name='uq_auth_code_user_purpose')
    )
    op.create_table('notifications',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=48), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), server_default='', nullable=False),
    sa.Column('link', sa.String(length=255), nullable=True),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_table('uploads',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('owner_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('key', sa.String(length=255), nullable=False),
    sa.Column('content_type', sa.String(length=64), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key')
    )
    op.create_index(op.f('ix_uploads_owner_id'), 'uploads', ['owner_id'], unique=False)
    op.create_table('creator_profiles',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('display_name', sa.String(length=80), nullable=False),
    sa.Column('bio', sa.Text(), nullable=True),
    sa.Column('photo_upload_id', sa.UUID(), nullable=True),
    sa.Column('interests', postgresql.ARRAY(sa.String(length=40)), server_default='{}', nullable=False),
    sa.Column('intended_platforms', postgresql.ARRAY(sa.String(length=20)), server_default='{}', nullable=False),
    sa.Column('discovery_source', sa.String(length=60), nullable=True),
    sa.Column('experience', sa.String(length=80), nullable=True),
    sa.Column('goals', postgresql.ARRAY(sa.String(length=80)), server_default='{}', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['photo_upload_id'], ['uploads.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('organisation_profiles',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('bio', sa.Text(), nullable=True),
    sa.Column('website', sa.String(length=255), nullable=True),
    sa.Column('photo_upload_id', sa.UUID(), nullable=True),
    sa.Column('finance_email', sa.String(length=255), nullable=True),
    sa.Column('business_legal_name', sa.String(length=160), nullable=True),
    sa.Column('business_verified', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('production_workflow', sa.String(length=60), nullable=True),
    sa.Column('team_size', sa.String(length=40), nullable=True),
    sa.Column('campaign_goal', sa.String(length=80), nullable=True),
    sa.Column('budget_range', sa.String(length=60), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['photo_upload_id'], ['uploads.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.add_column('social_accounts', sa.Column('handle', sa.String(length=255), nullable=True))
    op.add_column('social_accounts', sa.Column('display_name', sa.String(length=255), nullable=True))
    op.add_column('user_preferences', sa.Column('notifications', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    # Accounts that existed before verification was introduced were never
    # asked for a code; locking them out of spending actions now would be a
    # regression, so they are grandfathered in as verified.
    op.execute("UPDATE users SET email_verified = true, email_verified_at = now()")
    op.add_column('users', sa.Column('onboarded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('tokens_valid_after', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'tokens_valid_after')
    op.drop_column('users', 'onboarded_at')
    op.drop_column('users', 'email_verified_at')
    op.drop_column('users', 'email_verified')
    op.drop_column('user_preferences', 'notifications')
    op.drop_column('social_accounts', 'display_name')
    op.drop_column('social_accounts', 'handle')
    op.drop_table('organisation_profiles')
    op.drop_table('creator_profiles')
    op.drop_index(op.f('ix_uploads_owner_id'), table_name='uploads')
    op.drop_table('uploads')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_table('auth_codes')
    sa.Enum(name='auth_code_purpose').drop(op.get_bind(), checkfirst=True)
