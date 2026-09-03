"""Shared fixtures for system-behaviour scenario tests (Sprint 47.1).

Provides: in-memory SQLite DB, tenant A/B, plan seeding, tool spy
registry, and a ``run_facade`` helper that chains orchestrator → executor
via ``plan_and_execute``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.agent.base import AgentContext, AgentResult
from api.app.agent.facade import plan_and_execute
from api.app.agent.factory import get_agent
from api.app.agent.llm import LlmResult, StubChatModel, ToolCall, ToolSchema
from api.app.db.models import (
    AgentPlan,
    AgentPlanStep,
    AgentRun,
    McpServer,
    Tenant,
    ToolRegistry,
    WorkflowTemplate,
)
from api.app.db.plan_store import (
    get_agent_plan,
    insert_agent_plan,
    insert_agent_plan_step,
    list_agent_plan_steps,
    list_agent_runs,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):  # noqa: ANN001
    return "TEXT"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(_type, _compiler, **_kw):  # noqa: ANN001
    return "CHAR(32)"


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for model in (
        Tenant, WorkflowTemplate, McpServer, ToolRegistry,
        AgentPlan, AgentPlanStep, AgentRun,
    ):
        model.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def tenant_a(db: Session) -> Tenant:
    t = Tenant(id=uuid4(), slug=f"a-{uuid4().hex[:8]}", name="A", status="active")
    db.add(t)
    db.commit()
    return t


@pytest.fixture
def tenant_b(db: Session) -> Tenant:
    t = Tenant(id=uuid4(), slug=f"b-{uuid4().hex[:8]}", name="B", status="active")
    db.add(t)
    db.commit()
    return t


def add_template(
    db: Session,
    tenant: Tenant,
    *,
    title: str,
    body: str,
    created_at: datetime | None = None,
) -> WorkflowTemplate:
    """Insert a workflow_templates row for scenario setup."""
    now = created_at or datetime.now(timezone.utc)
    row = WorkflowTemplate(
        tenant_id=tenant.id,
        title=title,
        storage_relative_path=f"wf/{uuid4().hex}.md",
        content_hash=uuid4().hex,
        original_filename=f"{title}.md",
        body_text=body,
        visibility="shared",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def make_spy(name: str = "spy") -> MagicMock:
    """A tool spy that records calls but always returns success."""
    return MagicMock(
        side_effect=lambda arguments: {"ok": True, "tool": name},
    )


def make_boom(reason: str = "must not be called") -> MagicMock:
    """A tool that fails the test if invoked."""
    return MagicMock(side_effect=AssertionError(reason))


def plan_json(steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {"steps": steps}


@pytest.fixture(autouse=True)
def _block_orchestrator_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure orchestrator never calls library-mutate or MCP tools."""
    boom = MagicMock(side_effect=AssertionError("orchestrator must not run work tools"))
    for path in (
        "api.app.workflows.library.copy_template",
        "api.app.workflows.library.update_personal_draft",
        "api.app.workflows.library.store_from_attached_evidence",
        "api.app.workflows.library.store_workflow_template",
        "api.app.agent.mcp_client.call_mcp_tool",
    ):
        monkeypatch.setattr(path, boom, raising=False)


class _ExecutorStubModel:
    """Chat model that replays plan steps as tool calls, one per round.

    When all steps have been called (or a tool result indicates failure),
    it returns a text-only response to exit the loop.
    """

    def __init__(self, steps: list[dict[str, Any]], available_tools: set[str]) -> None:
        self._queue: list[dict[str, Any]] = list(steps)
        self._available_tools = available_tools
        self._done = False

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        model_tier: str,
        tools: list[ToolSchema] | None = None,
        **_kwargs: Any,
    ) -> LlmResult:
        last_msg = messages[-1]["content"] if messages else ""
        if "FAILED" in last_msg or "ERROR" in last_msg:
            self._done = True
            return LlmResult(
                text="Stopping due to failure.",
                model="stub-executor",
                input_tokens=10,
                output_tokens=10,
            )

        if self._done or not self._queue:
            return LlmResult(
                text="All steps completed.",
                model="stub-executor",
                input_tokens=10,
                output_tokens=10,
            )

        step = self._queue.pop(0)
        name = step.get("tool_name", "")
        args = step.get("arguments", {})
        return LlmResult(
            text="",
            model="stub-executor",
            input_tokens=10,
            output_tokens=10,
            tool_calls=(ToolCall(name=name, arguments=args, id=f"call_{name}"),),
        )


def run_facade(
    db: Session,
    tenant: Tenant,
    question: str,
    scripted_steps: list[dict[str, Any]] | None,
    *,
    tools: dict[str, Any] | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> AgentResult:
    """Run the full plan_and_execute facade with a scripted stub LLM.

    ``scripted_steps`` become the orchestrator's planned steps via StubChatModel.
    The executor uses an ``_ExecutorStubModel`` that replays those steps as
    tool calls in sequence.
    ``tools`` are injected into the executor's lookup context.
    """
    orchestrator_stub = StubChatModel(
        scripted_text=plan_json(scripted_steps) if scripted_steps is not None else None
    )
    available = set((tools or {}).keys())
    executor_stub = _ExecutorStubModel(
        list(scripted_steps or []), available
    )

    class _DualModel:
        """Routes to orchestrator stub for planning, executor stub for execution."""
        def __init__(self) -> None:
            self._first_call = True

        def complete(self, **kwargs: Any) -> LlmResult:
            if self._first_call:
                self._first_call = False
                return orchestrator_stub.complete(**kwargs)
            return executor_stub.complete(**kwargs)

    extra: dict[str, Any] = {
        "db": db,
        "chat_model": _DualModel(),
        "tools": tools or {},
    }
    return plan_and_execute(
        client_id=str(tenant.id),
        question=question,
        attachments=attachments,
        extra=extra,
    )
