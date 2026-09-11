"""Add encrypted OAuth token bundle on mcp_servers.

Revision ID: c8d2a91e4f70
Revises: a9c4e71f2b80
Create Date: 2026-09-07 23:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c8d2a91e4f70"
down_revision: Union[str, None] = "a9c4e71f2b80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mcp_servers",
        sa.Column("oauth_secret_encrypted", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mcp_servers", "oauth_secret_encrypted")
