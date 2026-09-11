"""Add encrypted service credentials on mcp_servers.

Revision ID: a9c4e71f2b80
Revises: b7e4f91c2a80
Create Date: 2026-09-06 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a9c4e71f2b80"
down_revision: Union[str, None] = "b7e4f91c2a80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mcp_servers",
        sa.Column("secret_encrypted", sa.Text(), nullable=True),
    )
    op.create_index(
        "uq_mcp_servers_tenant_name",
        "mcp_servers",
        ["tenant_id", "name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_mcp_servers_tenant_name", table_name="mcp_servers")
    op.drop_column("mcp_servers", "secret_encrypted")
