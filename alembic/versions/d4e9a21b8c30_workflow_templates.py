"""workflow_templates for shared Slack workflow library

Revision ID: d4e9a21b8c30
Revises: c3d8f12a9b20
Create Date: 2026-08-10 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d4e9a21b8c30"
down_revision: Union[str, None] = "c3d8f12a9b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_slack_file_id", sa.String(length=64), nullable=True),
        sa.Column("storage_relative_path", sa.String(length=512), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("created_by_slack_user_id", sa.String(length=64), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("owner_slack_user_id", sa.String(length=64), nullable=True),
        sa.Column("visibility", sa.String(length=32), nullable=False, server_default="shared"),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_id"], ["workflow_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_workflow_templates_tenant_id"),
        "workflow_templates",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_templates_source_slack_file_id"),
        "workflow_templates",
        ["source_slack_file_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_templates_content_hash"),
        "workflow_templates",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_templates_created_by_user_id"),
        "workflow_templates",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_templates_owner_slack_user_id"),
        "workflow_templates",
        ["owner_slack_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_templates_visibility"),
        "workflow_templates",
        ["visibility"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_templates_parent_id"),
        "workflow_templates",
        ["parent_id"],
        unique=False,
    )
    # Idempotent shared originals: one shared row per tenant + content hash
    op.create_index(
        "uq_workflow_templates_tenant_hash_shared",
        "workflow_templates",
        ["tenant_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text(
            "visibility = 'shared' AND parent_id IS NULL"
        ),
    )
    # Idempotent shared originals by Slack file id when present
    op.create_index(
        "uq_workflow_templates_tenant_slack_file_shared",
        "workflow_templates",
        ["tenant_id", "source_slack_file_id"],
        unique=True,
        postgresql_where=sa.text(
            "visibility = 'shared' AND parent_id IS NULL "
            "AND source_slack_file_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_workflow_templates_tenant_slack_file_shared",
        table_name="workflow_templates",
    )
    op.drop_index(
        "uq_workflow_templates_tenant_hash_shared",
        table_name="workflow_templates",
    )
    op.drop_index(op.f("ix_workflow_templates_parent_id"), table_name="workflow_templates")
    op.drop_index(op.f("ix_workflow_templates_visibility"), table_name="workflow_templates")
    op.drop_index(
        op.f("ix_workflow_templates_owner_slack_user_id"),
        table_name="workflow_templates",
    )
    op.drop_index(
        op.f("ix_workflow_templates_created_by_user_id"),
        table_name="workflow_templates",
    )
    op.drop_index(op.f("ix_workflow_templates_content_hash"), table_name="workflow_templates")
    op.drop_index(
        op.f("ix_workflow_templates_source_slack_file_id"),
        table_name="workflow_templates",
    )
    op.drop_index(op.f("ix_workflow_templates_tenant_id"), table_name="workflow_templates")
    op.drop_table("workflow_templates")
