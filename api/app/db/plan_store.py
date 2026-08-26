"""Tenant-scoped plan, step, and run persistence.

Tool and MCP server CRUD lives in ``tool_store.py``. This module
re-exports those symbols for backward compatibility with existing imports.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db.models import AgentPlan, AgentPlanStep, AgentRun
from api.app.db.tool_store import (  # noqa: F401 — re-export for back-compat
    TenantIdRequired,
    decrypt_tool_secret,
    delete_tool_registry,
    get_tool_registry,
    insert_mcp_server,
    insert_tool_registry,
    list_mcp_servers,
    list_tool_registry,
    require_tenant_id,
    update_tool_registry,
)
from api.app.db.tool_store import _tenant_uuid


# ── Plans ──


def insert_agent_plan(
    db: Session,
    *,
    tenant_id: str | UUID | None,
    question: str,
    source: dict[str, Any] | None = None,
    status: str = "draft",
    plan_json: dict[str, Any] | None = None,
) -> AgentPlan:
    tid = _tenant_uuid(tenant_id, where="insert_agent_plan")
    row = AgentPlan(
        tenant_id=tid,
        question=question,
        source=source,
        status=status,
        plan_json=plan_json,
    )
    db.add(row)
    db.flush()
    return row


def get_agent_plan(
    db: Session,
    *,
    tenant_id: str | UUID | None,
    plan_id: UUID | str,
) -> AgentPlan | None:
    tid = _tenant_uuid(tenant_id, where="get_agent_plan")
    return db.scalar(
        select(AgentPlan).where(
            AgentPlan.id == UUID(str(plan_id)),
            AgentPlan.tenant_id == tid,
        )
    )


def list_agent_plans(db: Session, *, tenant_id: str | UUID | None) -> list[AgentPlan]:
    tid = _tenant_uuid(tenant_id, where="list_agent_plans")
    return list(db.scalars(select(AgentPlan).where(AgentPlan.tenant_id == tid)).all())


# ── Plan steps ──


def insert_agent_plan_step(
    db: Session,
    *,
    tenant_id: str | UUID | None,
    plan_id: UUID,
    step_index: int,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    success_criteria: dict[str, Any] | str | None = None,
    status: str = "pending",
) -> AgentPlanStep:
    tid = _tenant_uuid(tenant_id, where="insert_agent_plan_step")
    criteria = success_criteria
    if isinstance(success_criteria, str):
        criteria = {"text": success_criteria}
    row = AgentPlanStep(
        tenant_id=tid,
        plan_id=plan_id,
        step_index=step_index,
        tool_name=tool_name,
        arguments=arguments,
        success_criteria=criteria,
        status=status,
    )
    db.add(row)
    db.flush()
    return row


def list_agent_plan_steps(
    db: Session,
    *,
    tenant_id: str | UUID | None,
    plan_id: UUID | str | None = None,
) -> list[AgentPlanStep]:
    tid = _tenant_uuid(tenant_id, where="list_agent_plan_steps")
    stmt = select(AgentPlanStep).where(AgentPlanStep.tenant_id == tid)
    if plan_id is not None:
        stmt = stmt.where(AgentPlanStep.plan_id == UUID(str(plan_id)))
    return list(db.scalars(stmt.order_by(AgentPlanStep.step_index)).all())


# ── Runs ──


def insert_agent_run(
    db: Session,
    *,
    tenant_id: str | UUID | None,
    plan_id: UUID,
    slack: dict[str, Any] | None = None,
    status: str = "pending",
) -> AgentRun:
    tid = _tenant_uuid(tenant_id, where="insert_agent_run")
    row = AgentRun(
        tenant_id=tid,
        plan_id=plan_id,
        slack=slack,
        status=status,
    )
    db.add(row)
    db.flush()
    return row


def list_agent_runs(
    db: Session,
    *,
    tenant_id: str | UUID | None,
    plan_id: UUID | str | None = None,
) -> list[AgentRun]:
    tid = _tenant_uuid(tenant_id, where="list_agent_runs")
    stmt = select(AgentRun).where(AgentRun.tenant_id == tid)
    if plan_id is not None:
        stmt = stmt.where(AgentRun.plan_id == UUID(str(plan_id)))
    return list(db.scalars(stmt).all())
