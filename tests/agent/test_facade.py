"""Facade end-to-end invariants (Sprint 46.3). Stub LLM + injected tools; no live Slack."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.agent.facade import plan_and_execute
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
    Tenant.__table__.create(engine)
    WorkflowTemplate.__table__.create(engine)
    McpServer.__table__.create(engine)
    ToolRegistry.__table__.create(engine)
    AgentPlan.__table__.create(engine)
    AgentPlanStep.__table__.create(engine)
    AgentRun.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def tenant(db: Session) -> Tenant:
    t = Tenant(id=uuid4(), slug=f"t-{uuid4().hex[:8]}", name="T", status="active")
    db.add(t)
    db.commit()
    return t


class _ExecutorStubModel:
    """Replays plan steps as tool calls, one per round."""

    def __init__(self, steps: list[dict[str, Any]]) -> None:
        self._queue = list(steps)
        self._done = False

    def complete(self, *, system: str, messages: list[dict[str, str]],
                 model_tier: str, tools: list[ToolSchema] | None = None,
                 **_kwargs: Any) -> LlmResult:
        last_msg = messages[-1]["content"] if messages else ""
        if "FAILED" in last_msg or "ERROR" in last_msg:
            self._done = True
            return LlmResult(text="Stopping.", model="stub", input_tokens=1, output_tokens=1)
        if self._done or not self._queue:
            return LlmResult(text="Done.", model="stub", input_tokens=1, output_tokens=1)
        step = self._queue.pop(0)
        return LlmResult(
            text="", model="stub", input_tokens=1, output_tokens=1,
            tool_calls=(ToolCall(name=step["tool_name"], arguments=step.get("arguments", {}), id="c"),),
        )


def _dual_model(steps: list[dict[str, Any]]) -> Any:
    """Returns a model that acts as orchestrator on first call, executor after."""
    orch = StubChatModel(scripted_text={"steps": steps})
    exe = _ExecutorStubModel(steps)

    class _Dual:
        def __init__(self) -> None:
            self._first = True
        def complete(self, **kw: Any) -> LlmResult:
            if self._first:
                self._first = False
                return orch.complete(**kw)
            return exe.complete(**kw)

    return _Dual()


def _noop_tool(**kwargs: Any) -> dict[str, Any]:
    return {"ok": True}


def _failing_tool(**kwargs: Any) -> dict[str, Any]:
    return {"ok": False, "error": "boom"}


class TestHappyPath:
    def test_orchestrator_then_executor_succeeds(self, db: Session, tenant: Tenant) -> None:
        steps = [{"tool_name": "do_thing", "arguments": {}, "success_criteria": "done"}]
        model = _dual_model(steps)
        result = plan_and_execute(
            client_id=str(tenant.id),
            question="do the thing",
            extra={
                "db": db,
                "chat_model": model,
                "tools": {"do_thing": _noop_tool},
            },
        )
        assert result.status == "succeeded"
        assert result.extra["plan_id"] is not None
        assert result.extra["run_id"] is not None
        assert result.extra["phase"] == "executor"
        assert result.role == "facade"


class TestOrchestratorFailure:
    def test_no_steps_means_no_executor(self, db: Session, tenant: Tenant) -> None:
        model = StubChatModel(scripted_text="I have no plan for you.")
        result = plan_and_execute(
            client_id=str(tenant.id),
            question="do something impossible",
            extra={
                "db": db,
                "chat_model": model,
            },
        )
        assert result.status == "failed"
        assert result.extra["phase"] == "orchestrator"
        assert result.extra.get("plan_id") is not None
        runs = db.query(AgentRun).all()
        assert len(runs) == 0, "executor should not have been called"


class TestExecutorStepFailure:
    def test_tool_returns_error(self, db: Session, tenant: Tenant) -> None:
        steps = [{"tool_name": "bad_tool", "arguments": {}, "success_criteria": "ok"}]
        model = _dual_model(steps)
        result = plan_and_execute(
            client_id=str(tenant.id),
            question="run bad tool",
            extra={
                "db": db,
                "chat_model": model,
                "tools": {"bad_tool": _failing_tool},
            },
        )
        assert result.status == "failed"
        assert result.extra["phase"] == "executor"
        assert result.extra["plan_id"] is not None
        assert result.extra["run_id"] is not None

    def test_missing_tool_fails(self, db: Session, tenant: Tenant) -> None:
        steps = [{"tool_name": "nonexistent", "arguments": {}, "success_criteria": "ok"}]
        model = _dual_model(steps)
        result = plan_and_execute(
            client_id=str(tenant.id),
            question="run missing tool",
            extra={
                "db": db,
                "chat_model": model,
            },
        )
        assert result.status == "failed"
        assert result.extra["phase"] == "executor"
