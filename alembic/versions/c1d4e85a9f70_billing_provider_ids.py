"""billing_customers provider-neutral external ids (Sprint 34.2)

Revision ID: c1d4e85a9f70
Revises: a8f3b12c4d56
Create Date: 2026-08-12 17:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c1d4e85a9f70"
down_revision: Union[str, None] = "a8f3b12c4d56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "billing_customers",
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="stripe"),
    )
    op.add_column(
        "billing_customers",
        sa.Column("external_customer_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "billing_customers",
        sa.Column("external_subscription_id", sa.String(length=255), nullable=True),
    )
    op.execute(
        """
        UPDATE billing_customers
        SET external_customer_id = stripe_customer_id,
            external_subscription_id = stripe_subscription_id
        """
    )
    # Drop unique constraint / index on stripe_customer_id (name varies by dialect)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for uc in inspector.get_unique_constraints("billing_customers"):
        cols = uc.get("column_names") or []
        if cols == ["stripe_customer_id"] or "stripe_customer_id" in cols:
            op.drop_constraint(uc["name"], "billing_customers", type_="unique")
    for ix in inspector.get_indexes("billing_customers"):
        cols = ix.get("column_names") or []
        if cols == ["stripe_customer_id"]:
            op.drop_index(ix["name"], table_name="billing_customers")

    op.drop_column("billing_customers", "stripe_customer_id")
    op.drop_column("billing_customers", "stripe_subscription_id")
    op.create_unique_constraint(
        "uq_billing_customers_external_customer_id",
        "billing_customers",
        ["external_customer_id"],
    )


def downgrade() -> None:
    op.add_column(
        "billing_customers",
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "billing_customers",
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
    )
    op.execute(
        """
        UPDATE billing_customers
        SET stripe_customer_id = external_customer_id,
            stripe_subscription_id = external_subscription_id
        """
    )
    op.drop_constraint(
        "uq_billing_customers_external_customer_id",
        "billing_customers",
        type_="unique",
    )
    op.drop_column("billing_customers", "external_subscription_id")
    op.drop_column("billing_customers", "external_customer_id")
    op.drop_column("billing_customers", "provider")
    op.create_unique_constraint(
        "billing_customers_stripe_customer_id_key",
        "billing_customers",
        ["stripe_customer_id"],
    )
