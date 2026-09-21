"""funding_orders.checkout_url (hosted checkout, Paystack)

Revision ID: c4d8e1f7a290
Revises: 6acb09f4e74b
"""

import sqlalchemy as sa
from alembic import op

revision = "c4d8e1f7a290"
down_revision = "6acb09f4e74b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("funding_orders", sa.Column("checkout_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("funding_orders", "checkout_url")
