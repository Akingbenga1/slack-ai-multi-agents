"""Orchestrator invariants (Sprint 44.3). Stub LLM + injected tools; no live Slack."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.agent.base import AgentContext
from api.app.agent.factory import get_agent
from api.app.agent.gather import wants_stored_workflow
from api.app.agent.llm import StubChatModel
from api.app.agent.orchestrator import (
    _PLAN_SYSTEM,
    _planning_user_message,
    parse_plan_steps,
)
from api.app.agent.guardrails import (
    PLAN_SAFETY_REFUSAL,
    find_destructive_plan_violations,
)
from api.app.agent.gather import GatheredContext
from api.app.db.models import AgentPlan, AgentPlanStep, McpServer, Tenant, ToolRegistry, WorkflowTemplate
from api.app.db.plan_store import get_agent_plan, list_agent_plan_steps, list_agent_plans


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):  # noqa: ANN001
    return "TEXT"


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Tenant.__table__.create(engine)
    WorkflowTemplate.__table__.create(engine)
    ToolRegistry.__table__.create(engine)
    McpServer.__table__.create(engine)
    AgentPlan.__table__.create(engine)
    AgentPlanStep.__table__.create(engine)
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


@pytest.fixture
def boom() -> MagicMock:
    return MagicMock(side_effect=AssertionError("orchestrator must not run work tools"))


@pytest.fixture(autouse=True)
def _block_work_side_effects(monkeypatch: pytest.MonkeyPatch, boom: MagicMock) -> None:
    monkeypatch.setattr(
        "api.app.workflows.library.copy_template", boom, raising=False
    )
    monkeypatch.setattr(
        "api.app.workflows.library.update_personal_draft", boom, raising=False
    )
    monkeypatch.setattr(
        "api.app.workflows.library.store_from_attached_evidence", boom, raising=False
    )
    monkeypatch.setattr(
        "api.app.workflows.library.store_workflow_template", boom, raising=False
    )
    monkeypatch.setattr(
        "api.app.agent.mcp_client.call_mcp_tool", boom, raising=False
    )


def _add_template(
    db: Session,
    tenant: Tenant,
    *,
    title: str,
    body: str,
    created_at: datetime | None = None,
) -> WorkflowTemplate:
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


def _plan_json(steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {"steps": steps}


class _RecordingModel:
    def __init__(self, inner: StubChatModel) -> None:
        self.inner = inner
        self.user_messages: list[str] = []

    def complete(self, **kwargs: Any) -> Any:
        messages = kwargs.get("messages") or []
        for item in messages:
            if item.get("role") == "user":
                self.user_messages.append(str(item.get("content") or ""))
        return self.inner.complete(**kwargs)


def _run(
    db: Session,
    tenant: Tenant,
    question: str,
    steps: list[dict[str, Any]] | None,
    *,
    attachments: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
    boom: MagicMock | None = None,
    record: bool = False,
) -> tuple[Any, _RecordingModel | StubChatModel]:
    inner = StubChatModel(
        scripted_text=_plan_json(steps) if steps is not None else None
    )
    model: _RecordingModel | StubChatModel = (
        _RecordingModel(inner) if record else inner
    )
    payload = dict(extra or {})
    payload["db"] = db
    payload["chat_model"] = model
    if steps is not None and "tools" not in payload:
        payload["tools"] = {
            str(step.get("tool_name") or "").strip(): (lambda **_kw: {"ok": True})
            for step in steps
            if str(step.get("tool_name") or "").strip()
        }
    if boom is not None:
        payload["post_slack_message"] = boom
        payload["store_workflow"] = boom
    result = get_agent("orchestrator").run(
        AgentContext(
            client_id=str(tenant.id),
            question=question,
            attachments=list(attachments or []),
            extra=payload,
        )
    )
    return result, model


def test_planning_user_message_is_english_goals_without_catalog():
    gathered = GatheredContext(
        question="Turn the spreadsheet into CSV",
        attachments=[{"filename": "a.xlsx"}],
        channels={},
        channel_names=[],
        workflow=None,
        wants_stored_workflow=False,
        workflow_error=None,
    )
    message = _planning_user_message(gathered)
    assert "execute_goal" in message
    assert "Shortlisted tool catalog" not in message
    assert "tool registry" in message.lower() or "Do not use a tool registry" in message
    assert "a.xlsx" in message


def test_parse_plan_steps_from_json_object():
    steps = parse_plan_steps(
        '{"steps": [{"tool_name": "fetch_channel_history", "arguments": {"ch": "#x"}}]}'
    )
    assert steps[0]["tool_name"] == "fetch_channel_history"
    assert steps[0]["arguments"]["ch"] == "#x"


def test_parse_plan_accepts_advice_steps_without_catalog_tool():
    steps = parse_plan_steps(
        json.dumps(
            {
                "workflow": "qa",
                "steps": [
                    {
                        "step_type": "advice",
                        "advice": "Attach the document and ask for a summary.",
                        "success_criteria": "User knows next step",
                    },
                    {
                        "tool_name": "csvkit",
                        "arguments": {"subcommand": "csvstat", "args_list": ["data.csv"]},
                        "success_criteria": "stats returned",
                    },
                ],
            }
        )
    )
    assert len(steps) == 2
    assert steps[0]["tool_name"] == "advice"
    assert steps[0]["arguments"]["text"] == "Attach the document and ask for a summary."
    assert steps[0]["step_type"] == "advice"
    assert steps[1]["tool_name"] == "csvkit"


def test_parse_plan_accepts_halt_steps():
    steps = parse_plan_steps(
        json.dumps(
            {
                "workflow": "qa",
                "steps": [
                    {
                        "step_type": "halt",
                        "message": "No file attached — please upload a document.",
                    }
                ],
            }
        )
    )
    assert len(steps) == 1
    assert steps[0]["tool_name"] == "halt"
    assert steps[0]["step_type"] == "halt"
    assert "No file attached" in steps[0]["arguments"]["text"]


def test_parse_plan_extracts_preconditions_on_tool_steps():
    steps = parse_plan_steps(
        json.dumps(
            {
                "workflow": "qa",
                "steps": [
                    {
                        "tool_name": "parse_file",
                        "requires_attachment": True,
                        "on_precondition_fail": "Attach a file first.",
                        "arguments": {},
                    }
                ],
            }
        )
    )
    assert steps[0]["preconditions"]["requires_attachment"] is True
    assert steps[0]["on_precondition_fail"] == "Attach a file first."


def test_store_request_is_not_a_stored_workflow_run():
    assert not wants_stored_workflow(
        "Store this incident triage workflow in our shared library."
    )
    assert wants_stored_workflow(
        "Get me the workflow I defined and stored yesterday and get it to run immediately."
    )


def test_case_a_attachment_metadata_plan_does_not_post(
    db: Session, tenant_a: Tenant, boom: MagicMock
):
    steps = [
        {
            "tool_name": "download_slack_file",
            "arguments": {"slack_file_id": "F123EXCEL"},
            "success_criteria": "bytes available",
        },
        {
            "tool_name": "parse_spreadsheet",
            "arguments": {"filename": "finance.xlsx"},
            "success_criteria": "figures extracted",
        },
        {
            "tool_name": "create_powerpoint",
            "arguments": {"pages": 3},
            "success_criteria": "pptx exists",
        },
        {
            "tool_name": "upload_to_slack",
            "arguments": {"thread": True},
            "success_criteria": "file uploaded",
        },
    ]
    result, _ = _run(
        db,
        tenant_a,
        "Create a 3 page financial report pptx from the excel file I just uploaded here in Slack.",
        steps,
        attachments=[
            {
                "filename": "finance.xlsx",
                "mimetype": "application/vnd.ms-excel",
                "file_id": "F123EXCEL",
                "text": "PARSED SHEET MUST NOT BE PLANNING CONTEXT",
            }
        ],
        boom=boom,
        record=True,
    )
    assert result.status == "ready"
    plan = get_agent_plan(
        db, tenant_id=str(tenant_a.id), plan_id=result.extra["plan_id"]
    )
    assert plan is not None
    assert plan.status == "ready"
    names = [
        s.tool_name
        for s in list_agent_plan_steps(
            db, tenant_id=str(tenant_a.id), plan_id=plan.id
        )
    ]
    assert names == [
        "download_slack_file",
        "parse_spreadsheet",
        "create_powerpoint",
        "upload_to_slack",
    ]
    source = plan.source or {}
    assert source["attachments"][0]["filename"] == "finance.xlsx"
    assert source["attachments"][0]["slack_file_id"] == "F123EXCEL"
    assert "text" not in source["attachments"][0]
    assert "PARSED SHEET" not in str(source)
    boom.assert_not_called()


def test_case_b_summarise_and_post_does_not_post(
    db: Session, tenant_a: Tenant, boom: MagicMock
):
    steps = [
        {
            "tool_name": "fetch_channel_history",
            "arguments": {"channel": "#product", "window": "yesterday"},
            "success_criteria": "messages fetched",
        },
        {
            "tool_name": "compose_summary",
            "arguments": {},
            "success_criteria": "grounded recap",
        },
        {
            "tool_name": "post_slack_message",
            "arguments": {"channel": "#leadership"},
            "success_criteria": "posted",
        },
    ]
    result, _ = _run(
        db,
        tenant_a,
        "Summarise yesterday’s discussion in #product and post the recap in #leadership.",
        steps,
        boom=boom,
    )
    assert result.status == "ready"
    names = [
        s.tool_name
        for s in list_agent_plan_steps(
            db, tenant_id=str(tenant_a.id), plan_id=result.extra["plan_id"]
        )
    ]
    assert names == [
        "fetch_channel_history",
        "compose_summary",
        "post_slack_message",
    ]
    boom.assert_not_called()


def test_case_c_run_stored_yesterday_uses_row_body_not_canned_incident(
    db: Session, tenant_a: Tenant, boom: MagicMock
):
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    body = "Send a rubber duck to #pond then assign a sticker."
    row = _add_template(
        db,
        tenant_a,
        title="Incident notes",
        body=body,
        created_at=yesterday,
    )
    steps = [
        {
            "tool_name": "post_slack_message",
            "arguments": {"channel": "#pond", "text": "rubber duck"},
            "success_criteria": "posted",
        },
        {
            "tool_name": "assign_sticker",
            "arguments": {},
            "success_criteria": "assigned",
        },
    ]
    result, model = _run(
        db,
        tenant_a,
        "Get me the workflow I defined and stored yesterday and get it to run immediately.",
        steps,
        boom=boom,
        record=True,
    )
    assert result.status == "ready"
    plan = get_agent_plan(
        db, tenant_id=str(tenant_a.id), plan_id=result.extra["plan_id"]
    )
    assert plan is not None
    assert plan.source["workflow_template_id"] == str(row.id)
    assert plan.source["workflow_body"] == body
    names = [
        s.tool_name
        for s in list_agent_plan_steps(
            db, tenant_id=str(tenant_a.id), plan_id=plan.id
        )
    ]
    assert names == ["post_slack_message", "assign_sticker"]
    assert "page_oncall" not in names
    assert "create_incident" not in names
    assert isinstance(model, _RecordingModel)
    assert body in model.user_messages[0]
    boom.assert_not_called()


def test_case_d_overrides_omit_laptop_and_leave_template_unchanged(
    db: Session, tenant_a: Tenant, boom: MagicMock
):
    body = (
        "1. Send a welcome note to #general.\n"
        "2. Request a laptop for the new hire.\n"
        "3. Add the hire to payroll."
    )
    row = _add_template(db, tenant_a, title="Onboarding", body=body)
    original = row.body_text
    steps = [
        {
            "tool_name": "post_slack_message",
            "arguments": {"channel": "#people", "text": "welcome"},
            "success_criteria": "welcome posted",
        },
        {
            "tool_name": "add_to_payroll",
            "arguments": {"start": "Monday"},
            "success_criteria": "payroll updated",
        },
    ]
    result, _ = _run(
        db,
        tenant_a,
        "Run the onboarding workflow for the new hire starting Monday, "
        "but skip the laptop request and send the welcome note to #people "
        "instead of #general.",
        steps,
        boom=boom,
    )
    assert result.status == "ready"
    planned = list_agent_plan_steps(
        db, tenant_id=str(tenant_a.id), plan_id=result.extra["plan_id"]
    )
    names = [s.tool_name for s in planned]
    assert "request_laptop" not in names
    assert all("laptop" not in (s.tool_name or "").lower() for s in planned)
    welcome = next(s for s in planned if s.tool_name == "post_slack_message")
    assert welcome.arguments["channel"] == "#people"
    db.refresh(row)
    assert row.body_text == original
    boom.assert_not_called()


def test_case_e_combined_plan_appends_unregistered_pdf_email(
    db: Session, tenant_a: Tenant, boom: MagicMock
):
    body = "Gather team status, compose a digest, post the digest to #status."
    _add_template(db, tenant_a, title="Weekly status", body=body)
    steps = [
        {
            "tool_name": "gather_status",
            "arguments": {},
            "success_criteria": "status collected",
        },
        {
            "tool_name": "compose_digest",
            "arguments": {},
            "success_criteria": "digest written",
        },
        {
            "tool_name": "post_slack_message",
            "arguments": {"channel": "#status"},
            "success_criteria": "posted",
        },
        {
            "tool_name": "generate_pdf",
            "arguments": {},
            "success_criteria": "pdf rendered",
        },
        {
            "tool_name": "send_email",
            "arguments": {},
            "success_criteria": "email sent",
        },
    ]
    result, _ = _run(
        db,
        tenant_a,
        "Run the weekly status workflow, then email me a PDF of the result.",
        steps,
        boom=boom,
    )
    assert result.status == "ready"
    names = [
        s.tool_name
        for s in list_agent_plan_steps(
            db, tenant_id=str(tenant_a.id), plan_id=result.extra["plan_id"]
        )
    ]
    assert names[:3] == ["gather_status", "compose_digest", "post_slack_message"]
    assert names[-2:] == ["generate_pdf", "send_email"]
    boom.assert_not_called()


def test_cross_tenant_cannot_read_other_workflow_templates(
    db: Session, tenant_a: Tenant, tenant_b: Tenant, boom: MagicMock
):
    secret = "TENANT B SECRET BODY — never attach to A"
    _add_template(db, tenant_b, title="Onboarding", body=secret)
    result, model = _run(
        db,
        tenant_a,
        "Run the onboarding workflow for the new hire.",
        None,
        boom=boom,
        record=True,
    )
    assert result.status == "failed"
    plan = get_agent_plan(
        db, tenant_id=str(tenant_a.id), plan_id=result.extra["plan_id"]
    )
    assert plan is not None
    assert plan.status == "failed"
    assert list_agent_plan_steps(
        db, tenant_id=str(tenant_a.id), plan_id=plan.id
    ) == []
    assert secret not in str(plan.source)
    assert secret not in str(plan.plan_json)
    if isinstance(model, _RecordingModel):
        assert model.user_messages == []
    assert list_agent_plans(db, tenant_id=str(tenant_b.id)) == []
    boom.assert_not_called()


def test_plan_system_includes_deletion_guardrails():
    assert "SAFETY GUARDRAILS" in _PLAN_SYSTEM
    assert "NEVER plan steps that delete" in _PLAN_SYSTEM
    assert "DROP or TRUNCATE tables" in _PLAN_SYSTEM


def test_plan_system_requires_english_execute_goal_steps():
    assert "execute_goal" in _PLAN_SYSTEM
    assert "plain English" in _PLAN_SYSTEM or "plain-English" in _PLAN_SYSTEM or "Plan in plain English" in _PLAN_SYSTEM
    assert "tool registry" in _PLAN_SYSTEM.lower() or "Do NOT use a tool registry" in _PLAN_SYSTEM
    assert "step_type" in _PLAN_SYSTEM and "advice" in _PLAN_SYSTEM
    assert "halt" in _PLAN_SYSTEM
    assert "requires_attachment" in _PLAN_SYSTEM
    assert "shortlisted tool catalog" not in _PLAN_SYSTEM


def test_plan_system_single_outcome_for_attached_transformations():
    assert "one execute_goal step" in _PLAN_SYSTEM
    assert "Do not add separate validation" in _PLAN_SYSTEM
def test_find_destructive_plan_violations_detects_delete_tool():
    violations = find_destructive_plan_violations(
        [{"tool_name": "delete_file", "arguments": {"path": "/tmp/a.txt"}}]
    )
    assert violations
    assert "delete_file" in violations[0]


def test_find_destructive_plan_violations_detects_destructive_sql():
    violations = find_destructive_plan_violations(
        [
            {
                "tool_name": "run_sql",
                "arguments": {"query": "DELETE FROM users WHERE id = 1"},
            }
        ]
    )
    assert violations
    assert "destructive SQL" in violations[0]


def test_find_destructive_plan_violations_detects_rm_in_cli_args():
    violations = find_destructive_plan_violations(
        [
            {
                "tool_name": "csvkit",
                "arguments": {
                    "subcommand": "custom",
                    "args_list": ["rm", "-rf", "/data/uploads"],
                },
            }
        ]
    )
    assert violations
    assert "destructive shell" in violations[0]


def test_destructive_plan_is_rejected_before_persisting_steps(
    db: Session, tenant_a: Tenant, boom: MagicMock
):
    steps = [
        {
            "tool_name": "delete_upload",
            "arguments": {"path": "data/uploads/report.pdf"},
            "success_criteria": "file removed",
        }
    ]
    result, _ = _run(
        db,
        tenant_a,
        "Delete the uploaded report.pdf from storage.",
        steps,
        boom=boom,
    )
    assert result.status == "failed"
    assert result.message == PLAN_SAFETY_REFUSAL
    plan = get_agent_plan(
        db, tenant_id=str(tenant_a.id), plan_id=result.extra["plan_id"]
    )
    assert plan is not None
    assert plan.status == "failed"
    assert list_agent_plan_steps(
        db, tenant_id=str(tenant_a.id), plan_id=plan.id
    ) == []
    boom.assert_not_called()


def test_missing_stored_workflow_writes_zero_steps(
    db: Session, tenant_a: Tenant, boom: MagicMock
):
    result, _ = _run(
        db,
        tenant_a,
        "Run the onboarding workflow for the new hire.",
        [
            {
                "tool_name": "should_not_be_used",
                "arguments": {},
                "success_criteria": "no",
            }
        ],
        boom=boom,
    )
    assert result.status == "failed"
    assert "No stored workflow matched" in result.message
    plan = get_agent_plan(
        db, tenant_id=str(tenant_a.id), plan_id=result.extra["plan_id"]
    )
    assert plan is not None
    assert plan.status == "failed"
    assert list_agent_plan_steps(
        db, tenant_id=str(tenant_a.id), plan_id=plan.id
    ) == []
    boom.assert_not_called()
