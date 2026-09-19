"""intelligence: sampled comment text

Comments are evidence, not observations: re-fetching upserts by the
platform's comment id rather than appending. Sentiment is not a column.

TikTok never writes here — its Display API has counts but not text.
X / Instagram / Facebook adapters that set `supports_comments` feed this
table; the trust rules only fire when a sample actually exists.

Revision ID: a1c8e4d2b6f0
Revises: f47c16b8e920
Create Date: 2026-09-19 18:55:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "a1c8e4d2b6f0"
down_revision: Union[str, None] = "f47c16b8e920"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RAW_JSON = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    op.create_table(
        "content_comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("platform_comment_id", sa.String(length=128), nullable=False),
        sa.Column("author_platform_user_id", sa.String(length=128), nullable=True),
        sa.Column("author_username", sa.String(length=255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("likes", sa.Integer(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw", RAW_JSON, nullable=False),
        sa.ForeignKeyConstraint(["content_id"], ["social_content.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "content_id", "platform_comment_id", name="uq_content_comment_identity"
        ),
    )
    op.create_index(
        "ix_content_comments_content_created",
        "content_comments",
        ["content_id", "posted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_content_comments_content_created", table_name="content_comments")
    op.drop_table("content_comments")
