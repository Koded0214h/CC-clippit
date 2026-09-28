"""engagement performance metrics and attribution

Revision ID: d2e7f4a9c1b3
Revises: a3d9f1c7e2b4
Create Date: 2026-09-28 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d2e7f4a9c1b3"
down_revision: Union[str, None] = "a3d9f1c7e2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("conversion_destination_type", sa.String(20), nullable=True))
    op.add_column("campaigns", sa.Column("conversion_destination_url", sa.String(2048), nullable=True))
    op.add_column("campaigns", sa.Column("conversion_whatsapp_number", sa.String(24), nullable=True))
    op.add_column("campaigns", sa.Column("attribution_window_days", sa.Integer(), server_default="30", nullable=False))
    op.add_column("campaigns", sa.Column("attribution_model", sa.String(20), server_default="last_touch", nullable=False))

    op.create_table(
        "campaign_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_type", sa.String(24), nullable=False),
        sa.Column("rate_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("unit_size", sa.Integer(), server_default="1", nullable=False),
        sa.Column("min_threshold", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("verification_method", sa.String(24), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint("rate_amount > 0", name="ck_campaign_metric_rate_positive"),
        sa.CheckConstraint("unit_size > 0", name="ck_campaign_metric_unit_positive"),
        sa.CheckConstraint("min_threshold >= 0", name="ck_campaign_metric_threshold_nonnegative"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "metric_type", name="uq_campaign_metric_type"),
    )
    op.create_index("ix_campaign_metrics_campaign_id", "campaign_metrics", ["campaign_id"])
    op.execute(
        """
        INSERT INTO campaign_metrics
            (id, campaign_id, metric_type, rate_amount, unit_size, min_threshold, verification_method, position)
        SELECT md5(concat(campaign_id::text, chr(58), 'view'))::uuid, campaign_id, 'view',
               rate_per_1000_views, 1000,
               min_views_threshold, 'platform', 0
        FROM campaign_payout_rules
        """
    )

    op.create_table(
        "attribution_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("short_code", sa.String(16), nullable=False),
        sa.Column("destination_url", sa.String(2048), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("last_visited_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        sa.UniqueConstraint("short_code"),
    )
    op.create_index("ix_attribution_links_campaign_id", "attribution_links", ["campaign_id"])
    op.create_index("ix_attribution_links_creator_id", "attribution_links", ["creator_id"])
    op.create_index("ix_attribution_links_submission_id", "attribution_links", ["submission_id"])
    op.create_index("ix_attribution_links_short_code", "attribution_links", ["short_code"])

    op.create_table(
        "campaign_integrations",
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("secret_last_four", sa.String(4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("campaign_id"),
    )

    op.create_table(
        "performance_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attribution_link_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("quantity", sa.BigInteger(), server_default="1", nullable=False),
        sa.Column("cumulative_total", sa.BigInteger(), nullable=True),
        sa.Column("value_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_event_id", sa.String(160), nullable=False),
        sa.Column("verification_status", sa.String(20), server_default="observed", nullable=False),
        sa.Column("fraud_status", sa.String(20), server_default="clear", nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint("quantity > 0", name="ck_performance_event_quantity_positive"),
        sa.ForeignKeyConstraint(["attribution_link_id"], ["attribution_links.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "source", "source_event_id", name="uq_performance_source_event"),
    )
    op.create_index("ix_performance_events_campaign_id", "performance_events", ["campaign_id"])
    op.create_index("ix_performance_events_creator_id", "performance_events", ["creator_id"])
    op.create_index("ix_performance_events_submission_id", "performance_events", ["submission_id"])
    op.create_index("ix_performance_events_attribution_link_id", "performance_events", ["attribution_link_id"])
    op.create_index("ix_performance_events_event_type", "performance_events", ["event_type"])
    op.create_index("ix_performance_events_created_at", "performance_events", ["created_at"])

    op.create_table(
        "metric_earning_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_type", sa.String(24), nullable=False),
        sa.Column("observed_total", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("billed_batches", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("accrued_amount", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("last_settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campaign_id", "creator_id", "submission_id", "metric_type", name="uq_metric_earning_account"
        ),
    )
    op.create_index("ix_metric_earning_accounts_campaign_id", "metric_earning_accounts", ["campaign_id"])
    op.create_index("ix_metric_earning_accounts_creator_id", "metric_earning_accounts", ["creator_id"])
    op.create_index("ix_metric_earning_accounts_submission_id", "metric_earning_accounts", ["submission_id"])

    op.add_column("earning_entries", sa.Column("metric_type", sa.String(24), server_default="view", nullable=False))
    op.add_column("earning_entries", sa.Column("billable_units", sa.BigInteger(), server_default="0", nullable=False))
    op.add_column("earning_entries", sa.Column("unit_size", sa.Integer(), server_default="1000", nullable=False))
    op.execute("UPDATE earning_entries SET billable_units = billable_views WHERE metric_type = 'view'")


def downgrade() -> None:
    op.drop_column("earning_entries", "unit_size")
    op.drop_column("earning_entries", "billable_units")
    op.drop_column("earning_entries", "metric_type")
    op.drop_table("metric_earning_accounts")
    op.drop_table("performance_events")
    op.drop_table("campaign_integrations")
    op.drop_table("attribution_links")
    op.drop_table("campaign_metrics")
    op.drop_column("campaigns", "attribution_model")
    op.drop_column("campaigns", "attribution_window_days")
    op.drop_column("campaigns", "conversion_whatsapp_number")
    op.drop_column("campaigns", "conversion_destination_url")
    op.drop_column("campaigns", "conversion_destination_type")
