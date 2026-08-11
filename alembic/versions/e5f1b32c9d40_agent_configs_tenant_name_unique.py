"""Unique (tenant_id, name) on agent_configs.

Revision ID: e5f1b32c9d40
Revises: d4e9a21b8c30
Create Date: 2026-08-10 20:45:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e5f1b32c9d40"
down_revision: Union[str, None] = "d4e9a21b8c30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep the newest row per (tenant_id, name); drop older duplicates.
    op.execute(
        """
        DELETE FROM agent_configs a
        USING agent_configs b
        WHERE a.tenant_id = b.tenant_id
          AND a.name = b.name
          AND a.created_at < b.created_at
        """
    )
    op.execute(
        """
        DELETE FROM agent_configs a
        USING agent_configs b
        WHERE a.tenant_id = b.tenant_id
          AND a.name = b.name
          AND a.created_at = b.created_at
          AND a.id < b.id
        """
    )
    op.create_unique_constraint(
        "uq_agent_configs_tenant_name",
        "agent_configs",
        ["tenant_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_agent_configs_tenant_name",
        "agent_configs",
        type_="unique",
    )
