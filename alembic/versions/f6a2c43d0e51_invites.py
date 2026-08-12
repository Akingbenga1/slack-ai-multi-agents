"""invites table for tokenised org-admin invites (Sprint 31.3)

Revision ID: f6a2c43d0e51
Revises: e5f1b32c9d40
Create Date: 2026-08-12 14:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f6a2c43d0e51"
down_revision: Union[str, None] = "e5f1b32c9d40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invites",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False, server_default="org_admin"),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invites_tenant_id"), "invites", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_invites_email"), "invites", ["email"], unique=False)
    op.create_index(op.f("ix_invites_token_hash"), "invites", ["token_hash"], unique=True)
    op.create_index(op.f("ix_invites_expires_at"), "invites", ["expires_at"], unique=False)
    op.create_index(
        op.f("ix_invites_created_by_user_id"), "invites", ["created_by_user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_invites_created_by_user_id"), table_name="invites")
    op.drop_index(op.f("ix_invites_expires_at"), table_name="invites")
    op.drop_index(op.f("ix_invites_token_hash"), table_name="invites")
    op.drop_index(op.f("ix_invites_email"), table_name="invites")
    op.drop_index(op.f("ix_invites_tenant_id"), table_name="invites")
    op.drop_table("invites")
