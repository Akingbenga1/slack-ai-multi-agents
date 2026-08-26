"""Seed search_knowledge as kind=code for all tenants.

Revision ID: b7e4f91c2a80
Revises: e8a1c47b3d90
Create Date: 2026-08-20 12:30:00.000000
"""

from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision: str = "b7e4f91c2a80"
down_revision: Union[str, None] = "e8a1c47b3d90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TOOL_NAME = "search_knowledge"
TOOL_KIND = "code"
TOOL_DESCRIPTION = "Search tenant knowledge base via RAG (in-process)"


def upgrade() -> None:
    conn = op.get_bind()
    tenants = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()
    for (tenant_id,) in tenants:
        exists = conn.execute(
            sa.text(
                "SELECT 1 FROM tool_registry "
                "WHERE tenant_id = :tid AND name = :name"
            ),
            {"tid": tenant_id, "name": TOOL_NAME},
        ).fetchone()
        if exists:
            conn.execute(
                sa.text(
                    "UPDATE tool_registry "
                    "SET kind = :kind, description = :desc "
                    "WHERE tenant_id = :tid AND name = :name"
                ),
                {
                    "kind": TOOL_KIND,
                    "desc": TOOL_DESCRIPTION,
                    "tid": tenant_id,
                    "name": TOOL_NAME,
                },
            )
            continue
        conn.execute(
            sa.text(
                "INSERT INTO tool_registry "
                "(id, tenant_id, name, kind, description) "
                "VALUES (:id, :tid, :name, :kind, :desc)"
            ),
            {
                "id": str(uuid4()),
                "tid": tenant_id,
                "name": TOOL_NAME,
                "kind": TOOL_KIND,
                "desc": TOOL_DESCRIPTION,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM tool_registry "
            "WHERE name = :name AND kind = :kind"
        ),
        {"name": TOOL_NAME, "kind": TOOL_KIND},
    )
