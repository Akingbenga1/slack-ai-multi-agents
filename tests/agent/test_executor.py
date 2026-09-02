"""Executor invariants (Sprint 48). LLM-driven executor with injected stub model."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.agent.base import AgentContext
from api.app.agent.factory import get_agent
from api.app.agent.llm import LlmResult, ToolCall, ToolSchema
from api.app.agent.tools import lookup_tool
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
    insert_mcp_server,
    insert_tool_registry,
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


class ScriptedChatModel:
    """Test chat model that plays back a sequence of LlmResults.

    Each call to ``complete`` pops and returns the next scripted response.
    After the script is exhausted, returns a text-only "done" response.
    """

    def __init__(self, responses: list[LlmResult]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        model_tier: str,
        tools: list[ToolSchema] | None = None,
    ) -> LlmResult:
        self._call_count += 1
        if self._responses:
            return self._responses.pop(0)
        return LlmResult(
            text="All steps completed.",
            model="stub",
            input_tokens=10,
            output_tokens=10,
        )

    @property
    def call_count(self) -> int:
        return self._call_count


def _make_tool_call(name: str, arguments: dict[str, Any] | None = None) -> LlmResult:
    """Helper: build an LlmResult with a single tool call."""
    return LlmResult(
        text="",
        model="stub",
        input_tokens=10,
        output_tokens=10,
        tool_calls=(ToolCall(name=name, arguments=arguments or {}, id=f"call_{name}"),),
    )


def _done_result(text: str = "All steps completed.") -> LlmResult:
    """Helper: build a text-only LlmResult (signals loop exit)."""
    return LlmResult(
        text=text,
        model="stub",
        input_tokens=10,
        output_tokens=10,
    )


def _seed_plan(
    db: Session,
    tenant: Tenant,
    *,
    question: str,
    steps: list[tuple[str, dict[str, Any] | None]],
) -> AgentPlan:
    plan = insert_agent_plan(
        db,
        tenant_id=str(tenant.id),
        question=question,
        status="ready",
        plan_json={"steps": [{"tool_name": n, "arguments": a or {}} for n, a in steps]},
    )
    for index, (name, args) in enumerate(steps):
        insert_agent_plan_step(
            db,
            tenant_id=str(tenant.id),
            plan_id=plan.id,
            step_index=index,
            tool_name=name,
            arguments=args or {},
            status="pending",
        )
    db.commit()
    return plan


def _run(
    db: Session,
    tenant: Tenant,
    plan: AgentPlan,
    tools: dict[str, Any],
    chat_model: ScriptedChatModel,
    **extra: Any,
):
    return get_agent("executor").run(
        AgentContext(
            client_id=str(tenant.id),
            question=plan.question,
            extra={
                "db": db,
                "plan_id": str(plan.id),
                "tools": tools,
                "chat_model": chat_model,
                **extra,
            },
        )
    )


def test_missing_plan_id_fails_closed(tenant_a: Tenant):
    result = get_agent("executor").run(
        AgentContext(client_id=str(tenant_a.id), question="run it")
    )
    assert result.status == "failed"
    assert "plan_id" in result.message


def test_cross_tenant_plan_refused(
    db: Session, tenant_a: Tenant, tenant_b: Tenant
):
    plan = _seed_plan(
        db, tenant_a, question="secret", steps=[("post_slack_message", {})]
    )
    boom = MagicMock(side_effect=AssertionError("must not run other tenant tools"))
    model = ScriptedChatModel([_done_result()])
    result = get_agent("executor").run(
        AgentContext(
            client_id=str(tenant_b.id),
            extra={
                "db": db,
                "plan_id": str(plan.id),
                "tools": {"post_slack_message": boom},
                "chat_model": model,
            },
        )
    )
    assert result.status == "failed"
    assert "not found" in result.message
    boom.assert_not_called()
    db.refresh(plan)
    assert plan.status == "ready"
    assert list_agent_runs(db, tenant_id=str(tenant_a.id), plan_id=plan.id) == []


def test_lookup_registry_is_tenant_scoped(
    db: Session, tenant_a: Tenant, tenant_b: Tenant
):
    insert_tool_registry(
        db, tenant_id=str(tenant_a.id), name="fetch_channel_history", kind="mcp"
    )
    db.commit()
    assert (
        lookup_tool(
            "fetch_channel_history",
            client_id=str(tenant_a.id),
            db=db,
            extra={},
        )
        is not None
    )
    assert (
        lookup_tool(
            "fetch_channel_history",
            client_id=str(tenant_b.id),
            db=db,
            extra={},
        )
        is None
    )


def test_lookup_unknown_mcp_url_is_not_found(
    db: Session, tenant_a: Tenant
):
    insert_mcp_server(
        db,
        tenant_id=str(tenant_a.id),
        name="mystery",
        transport="http",
        connection_config={"url": "https://example.invalid/mcp"},
        enabled=True,
    )
    db.commit()
    connected = MagicMock(side_effect=AssertionError("must not open unknown MCP URLs"))
    ref = lookup_tool(
        "create_powerpoint",
        client_id=str(tenant_a.id),
        db=db,
        extra={"call_mcp_tool": connected},
    )
    assert ref is None
    connected.assert_not_called()


def test_lookup_registry_tool_found(db: Session, tenant_a: Tenant):
    insert_tool_registry(
        db, tenant_id=str(tenant_a.id), name="search_knowledge", kind="mcp"
    )
    db.commit()
    ref = lookup_tool(
        "search_knowledge", client_id=str(tenant_a.id), db=db, extra={}
    )
    assert ref is not None
    assert ref.source == "registry"
    assert (
        lookup_tool(
            "create_powerpoint", client_id=str(tenant_a.id), db=db, extra={}
        )
        is None
    )


def test_empty_tool_name_not_executed(db: Session, tenant_a: Tenant):
    plan = _seed_plan(
        db,
        tenant_a,
        question="bad step",
        steps=[("", {}), ("post_slack_message", {})],
    )
    post = MagicMock(side_effect=AssertionError("must not run later steps"))
    model = ScriptedChatModel([_done_result()])
    result = _run(db, tenant_a, plan, {"post_slack_message": post}, model)
    assert result.status == "failed"
    assert "empty tool_name" in result.message
    post.assert_not_called()
    steps = list_agent_plan_steps(db, tenant_id=str(tenant_a.id), plan_id=plan.id)
    assert steps[0].status == "failed"
    assert steps[1].status == "skipped"


def test_advice_only_plan_succeeds_without_tools(db: Session, tenant_a: Tenant):
    plan = _seed_plan(
        db,
        tenant_a,
        question="Summarise a PDF with no tools registered",
        steps=[
            (
                "advice",
                {
                    "text": (
                        "No document parser is registered. Attach the file and "
                        "ask for a summary, or register a parse tool."
                    )
                },
            ),
        ],
    )
    model = ScriptedChatModel([_done_result()])
    result = _run(db, tenant_a, plan, {}, model)
    assert result.status == "succeeded"
    assert "No document parser is registered" in result.message
    steps = list_agent_plan_steps(db, tenant_id=str(tenant_a.id), plan_id=plan.id)
    assert steps[0].status == "succeeded"
    assert steps[0].result and "advice" in steps[0].result


def test_scenario1_missing_powerpoint_stops_without_upload(
    db: Session, tenant_a: Tenant
):
    plan = _seed_plan(
        db,
        tenant_a,
        question="Create a 3 page financial report pptx from the excel file",
        steps=[
            ("download_slack_file", {"file_id": "F1"}),
            ("parse_excel", {}),
            ("create_powerpoint", {"pages": 3}),
            ("upload_to_slack", {}),
        ],
    )
    calls: list[str] = []
    upload = MagicMock(side_effect=AssertionError("must not upload a fake PPTX"))
    tools = {
        "download_slack_file": lambda arguments: calls.append("download") or {"ok": True},
        "parse_excel": lambda arguments: calls.append("parse") or {"ok": True, "figures": [1]},
        "upload_to_slack": upload,
    }
    model = ScriptedChatModel([
        _make_tool_call("download_slack_file", {"file_id": "F1"}),
        _make_tool_call("parse_excel"),
        _make_tool_call("create_powerpoint", {"pages": 3}),
        _done_result("Failed: create_powerpoint tool not available."),
    ])
    result = _run(db, tenant_a, plan, tools, model)
    assert result.status == "failed"
    assert "create_powerpoint" in result.message
    assert calls == ["download", "parse"]
    upload.assert_not_called()
    steps = list_agent_plan_steps(db, tenant_id=str(tenant_a.id), plan_id=plan.id)
    assert [s.status for s in steps] == ["succeeded", "succeeded", "failed", "skipped"]
    assert steps[2].error and "create_powerpoint" in steps[2].error
    assert get_agent_plan(db, tenant_id=str(tenant_a.id), plan_id=plan.id).status == "failed"
    run = list_agent_runs(db, tenant_id=str(tenant_a.id), plan_id=plan.id)[0]
    assert run.status == "failed"


def test_scenario2_fetch_fail_does_not_invent_recap(
    db: Session, tenant_a: Tenant
):
    plan = _seed_plan(
        db,
        tenant_a,
        question="Summarise yesterday in #product and post to #leadership",
        steps=[
            ("fetch_channel_history", {"channel": "#product"}),
            ("compose_summary", {}),
            ("post_slack_message", {"channel": "#leadership"}),
        ],
    )
    calls: list[str] = []
    post = MagicMock(side_effect=AssertionError("must not post"))
    tools = {
        "fetch_channel_history": lambda arguments: (
            calls.append("fetch") or {"ok": False, "error": "history unavailable"}
        ),
        "compose_summary": lambda arguments: (
            calls.append("compose") or {"ok": True, "text": "INVENTED RECAP"}
        ),
        "post_slack_message": post,
    }
    model = ScriptedChatModel([
        _make_tool_call("fetch_channel_history", {"channel": "#product"}),
        _done_result("Failed: could not fetch channel history."),
    ])
    result = _run(db, tenant_a, plan, tools, model)
    assert result.status == "failed"
    assert "INVENTED RECAP" not in result.message
    assert calls == ["fetch"]
    post.assert_not_called()
    steps = list_agent_plan_steps(db, tenant_id=str(tenant_a.id), plan_id=plan.id)
    assert steps[0].status == "failed"
    assert steps[1].status == "skipped"
    assert steps[2].status == "skipped"


def test_scenario3_yesterday_store_does_not_run_body(
    db: Session, tenant_a: Tenant
):
    insert_tool_registry(
        db, tenant_id=str(tenant_a.id), name="store_workflow", kind="code"
    )
    db.commit()
    body = "Post to #incidents, assign severity, notify on-call."
    plan = _seed_plan(
        db,
        tenant_a,
        question="Store this incident triage workflow in our shared library",
        steps=[
            (
                "store_workflow",
                {"title": "Incident triage", "body_text": body, "filename": "triage.txt"},
            )
        ],
    )
    body_tools = {
        "post_incidents": MagicMock(side_effect=AssertionError("must not run body")),
        "assign_severity": MagicMock(side_effect=AssertionError("must not run body")),
        "notify_oncall": MagicMock(side_effect=AssertionError("must not run body")),
    }
    model = ScriptedChatModel([
        _make_tool_call("store_workflow", {
            "title": "Incident triage",
            "body_text": body,
            "filename": "triage.txt",
        }),
        _done_result("Workflow stored successfully."),
    ])
    result = _run(db, tenant_a, plan, body_tools, model)
    assert result.status == "succeeded"
    rows = list(
        db.scalars(
            select(WorkflowTemplate).where(WorkflowTemplate.tenant_id == tenant_a.id)
        ).all()
    )
    assert len(rows) == 1
    assert rows[0].title == "Incident triage"
    assert rows[0].body_text == body
    for spy in body_tools.values():
        spy.assert_not_called()


def test_scenario3_today_runs_only_listed_tools(
    db: Session, tenant_a: Tenant
):
    plan = _seed_plan(
        db,
        tenant_a,
        question="Run the workflow I stored yesterday",
        steps=[
            ("post_incidents", {"channel": "#incidents"}),
            ("assign_severity", {}),
            ("notify_oncall", {}),
        ],
    )
    calls: list[str] = []
    extra = MagicMock(side_effect=AssertionError("unlisted tool must not run"))
    tools = {
        "post_incidents": lambda arguments: calls.append("post") or {"ok": True},
        "assign_severity": lambda arguments: calls.append("assign") or {"ok": True},
        "notify_oncall": lambda arguments: calls.append("notify") or {"ok": True},
        "store_workflow": extra,
        "create_powerpoint": extra,
    }
    model = ScriptedChatModel([
        _make_tool_call("post_incidents", {"channel": "#incidents"}),
        _make_tool_call("assign_severity"),
        _make_tool_call("notify_oncall"),
        _done_result("All 3 steps completed."),
    ])
    result = _run(db, tenant_a, plan, tools, model)
    assert result.status == "succeeded"
    assert calls == ["post", "assign", "notify"]
    extra.assert_not_called()


def test_scenario4_override_skips_laptop_keeps_template(
    db: Session, tenant_a: Tenant
):
    original = "1. Request a laptop.\n2. Send welcome to #general."
    now = datetime.now(timezone.utc)
    template = WorkflowTemplate(
        tenant_id=tenant_a.id,
        title="Onboarding",
        storage_relative_path="workflows/onboarding.txt",
        content_hash="onboard-hash",
        original_filename="onboarding.txt",
        body_text=original,
        visibility="shared",
        created_at=now,
        updated_at=now,
    )
    db.add(template)
    db.commit()
    posted: list[dict[str, Any]] = []
    laptop = MagicMock(side_effect=AssertionError("laptop step must not run"))
    plan = _seed_plan(
        db,
        tenant_a,
        question="Run onboarding, skip laptop, welcome to #people",
        steps=[
            ("send_welcome_note", {"channel": "#people"}),
            ("create_accounts", {}),
        ],
    )
    tools = {
        "request_laptop": laptop,
        "send_welcome_note": lambda arguments: posted.append(dict(arguments))
        or {"ok": True},
        "create_accounts": lambda arguments: {"ok": True},
    }
    model = ScriptedChatModel([
        _make_tool_call("send_welcome_note", {"channel": "#people"}),
        _make_tool_call("create_accounts"),
        _done_result("Onboarding done."),
    ])
    result = _run(db, tenant_a, plan, tools, model)
    assert result.status == "succeeded"
    laptop.assert_not_called()
    assert posted and posted[0].get("channel") == "#people"
    db.refresh(template)
    assert template.body_text == original
    assert template.title == "Onboarding"


def test_scenario5_missing_email_does_not_claim_sent(
    db: Session, tenant_a: Tenant
):
    plan = _seed_plan(
        db,
        tenant_a,
        question="Run the weekly status workflow, then email me a PDF",
        steps=[
            ("gather_status", {}),
            ("compose_digest", {}),
            ("post_status", {}),
            ("generate_pdf", {}),
            ("send_email", {}),
        ],
    )
    calls: list[str] = []
    email = MagicMock(side_effect=AssertionError("must not send email"))
    tools = {
        "gather_status": lambda arguments: calls.append("gather") or {"ok": True},
        "compose_digest": lambda arguments: calls.append("compose") or {"ok": True},
        "post_status": lambda arguments: calls.append("post") or {"ok": True},
        "send_email": email,
    }
    model = ScriptedChatModel([
        _make_tool_call("gather_status"),
        _make_tool_call("compose_digest"),
        _make_tool_call("post_status"),
        _make_tool_call("generate_pdf"),
        _done_result("Failed: generate_pdf tool not available."),
    ])
    result = _run(db, tenant_a, plan, tools, model)
    assert result.status == "failed"
    assert "generate_pdf" in result.message
    assert calls == ["gather", "compose", "post"]
    email.assert_not_called()
    steps = list_agent_plan_steps(db, tenant_id=str(tenant_a.id), plan_id=plan.id)
    assert [s.status for s in steps] == [
        "succeeded",
        "succeeded",
        "succeeded",
        "failed",
        "skipped",
    ]
    assert all(s.result and s.result.get("ok") is True for s in steps[:3])


def test_llm_drives_tool_selection(db: Session, tenant_a: Tenant):
    """Sequential executor runs each planned tool step in order."""
    plan = _seed_plan(
        db,
        tenant_a,
        question="Fetch data and summarise",
        steps=[
            ("fetch_data", {"source": "api"}),
            ("summarise", {}),
        ],
    )
    calls: list[str] = []
    tools = {
        "fetch_data": lambda arguments: calls.append("fetch") or {"ok": True, "data": [1, 2]},
        "summarise": lambda arguments: calls.append("summarise") or {"ok": True, "text": "done"},
    }
    model = ScriptedChatModel([
        _make_tool_call("fetch_data", {"source": "api"}),
        _make_tool_call("summarise"),
        _done_result("Fetched data and summarised."),
    ])
    result = _run(db, tenant_a, plan, tools, model)
    assert result.status == "succeeded"
    assert calls == ["fetch", "summarise"]


def test_halt_step_stops_without_running_later_tools(db: Session, tenant_a: Tenant):
    plan = insert_agent_plan(
        db,
        tenant_id=str(tenant_a.id),
        question="Process file",
        status="ready",
        plan_json={"steps": []},
    )
    insert_agent_plan_step(
        db,
        tenant_id=str(tenant_a.id),
        plan_id=plan.id,
        step_index=0,
        tool_name="halt",
        arguments={
            "text": "No file attached — please upload a document.",
            "_step_meta": {"step_type": "halt", "stop_after": True},
        },
        status="pending",
    )
    later = MagicMock(side_effect=AssertionError("must not run after halt"))
    insert_agent_plan_step(
        db,
        tenant_id=str(tenant_a.id),
        plan_id=plan.id,
        step_index=1,
        tool_name="parse_file",
        arguments={},
        status="pending",
    )
    db.commit()
    result = _run(db, tenant_a, plan, {"parse_file": later}, ScriptedChatModel([]))
    assert result.status == "succeeded"
    assert "No file attached" in result.message
    later.assert_not_called()
    steps = list_agent_plan_steps(db, tenant_id=str(tenant_a.id), plan_id=plan.id)
    assert steps[0].status == "succeeded"
    assert steps[1].status == "skipped"


def test_precondition_fail_stops_later_steps(db: Session, tenant_a: Tenant):
    plan = insert_agent_plan(
        db,
        tenant_id=str(tenant_a.id),
        question="Summarise upload",
        status="ready",
        plan_json={"steps": []},
    )
    insert_agent_plan_step(
        db,
        tenant_id=str(tenant_a.id),
        plan_id=plan.id,
        step_index=0,
        tool_name="parse_file",
        arguments={
            "_step_meta": {
                "step_type": "tool",
                "preconditions": {"requires_attachment": True},
                "on_precondition_fail": "Please attach a file first.",
            }
        },
        status="pending",
    )
    parse = MagicMock(side_effect=AssertionError("must not parse without attachment"))
    insert_agent_plan_step(
        db,
        tenant_id=str(tenant_a.id),
        plan_id=plan.id,
        step_index=1,
        tool_name="summarise",
        arguments={},
        status="pending",
    )
    db.commit()
    result = _run(db, tenant_a, plan, {"parse_file": parse, "summarise": parse}, ScriptedChatModel([]))
    assert result.status == "succeeded"
    assert "Please attach a file first" in result.message
    parse.assert_not_called()
    steps = list_agent_plan_steps(db, tenant_id=str(tenant_a.id), plan_id=plan.id)
    assert steps[0].status == "skipped"
    assert steps[1].status == "skipped"


def test_advice_stop_after_blocks_later_tools(db: Session, tenant_a: Tenant):
    plan = insert_agent_plan(
        db,
        tenant_id=str(tenant_a.id),
        question="Need guidance",
        status="ready",
        plan_json={"steps": []},
    )
    insert_agent_plan_step(
        db,
        tenant_id=str(tenant_a.id),
        plan_id=plan.id,
        step_index=0,
        tool_name="advice",
        arguments={
            "text": "Register a parser tool first.",
            "_step_meta": {"step_type": "advice", "stop_after": True},
        },
        status="pending",
    )
    tool = MagicMock(side_effect=AssertionError("must not run after blocking advice"))
    insert_agent_plan_step(
        db,
        tenant_id=str(tenant_a.id),
        plan_id=plan.id,
        step_index=1,
        tool_name="parse_file",
        arguments={},
        status="pending",
    )
    db.commit()
    result = _run(db, tenant_a, plan, {"parse_file": tool}, ScriptedChatModel([]))
    assert result.status == "succeeded"
    assert "Register a parser tool first" in result.message
    tool.assert_not_called()


def test_advice_without_stop_after_continues_to_tools(db: Session, tenant_a: Tenant):
    plan = insert_agent_plan(
        db,
        tenant_id=str(tenant_a.id),
        question="Run with note",
        status="ready",
        plan_json={"steps": []},
    )
    insert_agent_plan_step(
        db,
        tenant_id=str(tenant_a.id),
        plan_id=plan.id,
        step_index=0,
        tool_name="advice",
        arguments={
            "text": "Starting processing.",
            "_step_meta": {"step_type": "advice", "stop_after": False},
        },
        status="pending",
    )
    insert_agent_plan_step(
        db,
        tenant_id=str(tenant_a.id),
        plan_id=plan.id,
        step_index=1,
        tool_name="fetch_data",
        arguments={},
        status="pending",
    )
    db.commit()
    calls: list[str] = []
    tools = {"fetch_data": lambda arguments: calls.append("fetch") or {"ok": True}}
    result = _run(db, tenant_a, plan, tools, ScriptedChatModel([]))
    assert result.status == "succeeded"
    assert "Starting processing" in result.message
    assert calls == ["fetch"]


def test_execute_goal_verifies_artifact_when_result_reports_failure(
    db: Session, tenant_a: Tenant, tmp_path: Path
):
    target = tmp_path / "Combined.pdf"
    target.write_bytes(b"%PDF-merged")
    plan = insert_agent_plan(
        db,
        tenant_id=str(tenant_a.id),
        question="Merge PDFs",
        status="ready",
        plan_json={"steps": []},
    )
    insert_agent_plan_step(
        db,
        tenant_id=str(tenant_a.id),
        plan_id=plan.id,
        step_index=0,
        tool_name="execute_goal",
        arguments={
            "instruction": "Merge uploaded PDFs",
            "cwd": str(tmp_path),
        },
        success_criteria="Combined PDF exists",
        status="pending",
    )
    db.commit()

    def fake_react(*, context, extra, db, instruction, success_criteria, step_arguments):
        return {
            "ok": False,
            "error": "executor stopped without success",
            "output_file": str(target),
            "attempts": [],
            "instruction": instruction,
        }

    import api.app.agent.executor as executor_module

    original = executor_module._run_english_goal_react
    executor_module._run_english_goal_react = fake_react
    try:
        result = _run(
            db,
            tenant_a,
            plan,
            {},
            ScriptedChatModel([_done_result()]),
        )
    finally:
        executor_module._run_english_goal_react = original

    assert result.status == "succeeded"
    steps = list_agent_plan_steps(db, tenant_id=str(tenant_a.id), plan_id=plan.id)
    assert steps[0].status == "succeeded"
    assert steps[0].result.get("verified") is True


def test_probe_only_execute_goal_fails_verification(db: Session, tenant_a: Tenant):
    plan = insert_agent_plan(
        db,
        tenant_id=str(tenant_a.id),
        question="Convert file",
        status="ready",
        plan_json={"steps": []},
    )
    insert_agent_plan_step(
        db,
        tenant_id=str(tenant_a.id),
        plan_id=plan.id,
        step_index=0,
        tool_name="execute_goal",
        arguments={"instruction": "Convert spreadsheet to CSV"},
        success_criteria="CSV file exists",
        status="pending",
    )
    db.commit()

    def fake_react(*, context, extra, db, instruction, success_criteria, step_arguments):
        return {
            "ok": True,
            "stdout": "Usage: in2csv ...",
            "attempts": [
                {"ok": True, "help_only": True, "args_list": ["--help"], "stdout": "Usage"},
            ],
            "instruction": instruction,
        }

    import api.app.agent.executor as executor_module

    original = executor_module._run_english_goal_react
    executor_module._run_english_goal_react = fake_react
    try:
        result = _run(
            db,
            tenant_a,
            plan,
            {},
            ScriptedChatModel([_done_result()]),
        )
    finally:
        executor_module._run_english_goal_react = original

    assert result.status == "failed"
    steps = list_agent_plan_steps(db, tenant_id=str(tenant_a.id), plan_id=plan.id)
    assert steps[0].status == "failed"
