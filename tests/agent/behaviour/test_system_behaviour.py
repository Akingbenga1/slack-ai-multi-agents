"""System-behaviour scenario tests (Sprint 47.2–47.3).

Maps 1:1 to ``system-behaviour.md`` Scenarios 1–5 plus cross-tenant
isolation. Offline: stub LLM + injected tools + in-memory SQLite.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db.models import AgentPlan, AgentPlanStep, Tenant, WorkflowTemplate
from api.app.db.plan_store import (
    get_agent_plan,
    list_agent_plan_steps,
    list_agent_plans,
    list_agent_runs,
)

from .conftest import add_template, make_boom, make_spy, run_facade


# ── Scenario 1: one-off instruction with an attachment ──


class TestScenario1:
    """Attachment metadata present; orchestrator does not call create_powerpoint;
    executor with tool missing → failed step names create_powerpoint."""

    QUESTION = (
        "Create a 3 page financial report pptx from the excel file "
        "I just uploaded here in Slack."
    )
    ATTACHMENTS = [
        {
            "filename": "finance.xlsx",
            "mimetype": "application/vnd.ms-excel",
            "file_id": "F123EXCEL",
        }
    ]
    STEPS = [
        {"tool_name": "download_slack_file", "arguments": {"file_id": "F123EXCEL"}, "success_criteria": "bytes available"},
        {"tool_name": "parse_spreadsheet", "arguments": {"filename": "finance.xlsx"}, "success_criteria": "figures extracted"},
        {"tool_name": "create_powerpoint", "arguments": {"pages": 3}, "success_criteria": "pptx exists"},
        {"tool_name": "upload_to_slack", "arguments": {"thread": True}, "success_criteria": "file uploaded"},
    ]

    def test_missing_powerpoint_stops_and_reports(
        self, db: Session, tenant_a: Tenant
    ):
        calls: list[str] = []
        upload = make_boom("must not upload a fake PPTX")
        tools = {
            "download_slack_file": lambda arguments: calls.append("download") or {"ok": True},
            "parse_spreadsheet": lambda arguments: calls.append("parse") or {"ok": True},
            "upload_to_slack": upload,
        }
        result = run_facade(
            db, tenant_a, self.QUESTION, self.STEPS,
            tools=tools, attachments=self.ATTACHMENTS,
        )
        assert result.status == "failed"
        assert "create_powerpoint" in result.message
        assert calls == ["download", "parse"]
        upload.assert_not_called()

        plan_id = result.extra["plan_id"]
        steps = list_agent_plan_steps(db, tenant_id=str(tenant_a.id), plan_id=plan_id)
        statuses = [s.status for s in steps]
        assert statuses == ["succeeded", "succeeded", "failed", "skipped"]
        assert steps[2].error and "create_powerpoint" in steps[2].error

    def test_all_tools_registered_succeeds(
        self, db: Session, tenant_a: Tenant
    ):
        calls: list[str] = []
        tools = {
            "download_slack_file": lambda arguments: calls.append("download") or {"ok": True},
            "parse_spreadsheet": lambda arguments: calls.append("parse") or {"ok": True},
            "create_powerpoint": lambda arguments: calls.append("pptx") or {"ok": True},
            "upload_to_slack": lambda arguments: calls.append("upload") or {"ok": True},
        }
        result = run_facade(
            db, tenant_a, self.QUESTION, self.STEPS,
            tools=tools, attachments=self.ATTACHMENTS,
        )
        assert result.status == "succeeded"
        assert calls == ["download", "parse", "pptx", "upload"]


# ── Scenario 2: one-off instruction with no file ──


class TestScenario2:
    """No attachment; orchestrator does not post; executor handles failures."""

    QUESTION = (
        "Summarise yesterday's discussion in #product and post the recap in #leadership."
    )
    STEPS = [
        {"tool_name": "fetch_channel_history", "arguments": {"channel": "#product", "window": "yesterday"}, "success_criteria": "messages fetched"},
        {"tool_name": "compose_summary", "arguments": {}, "success_criteria": "grounded recap"},
        {"tool_name": "post_slack_message", "arguments": {"channel": "#leadership"}, "success_criteria": "posted"},
    ]

    def test_missing_post_tool_fails(self, db: Session, tenant_a: Tenant):
        calls: list[str] = []
        tools = {
            "fetch_channel_history": lambda arguments: calls.append("fetch") or {"ok": True, "messages": ["m1"]},
            "compose_summary": lambda arguments: calls.append("compose") or {"ok": True, "text": "recap"},
        }
        result = run_facade(db, tenant_a, self.QUESTION, self.STEPS, tools=tools)
        assert result.status == "failed"
        assert "post_slack_message" in result.message
        assert calls == ["fetch", "compose"]

    def test_fetch_failure_does_not_invent_recap(self, db: Session, tenant_a: Tenant):
        calls: list[str] = []
        post = make_boom("must not post")
        tools = {
            "fetch_channel_history": lambda arguments: (
                calls.append("fetch") or {"ok": False, "error": "history unavailable"}
            ),
            "compose_summary": lambda arguments: (
                calls.append("compose") or {"ok": True, "text": "INVENTED RECAP"}
            ),
            "post_slack_message": post,
        }
        result = run_facade(db, tenant_a, self.QUESTION, self.STEPS, tools=tools)
        assert result.status == "failed"
        assert "INVENTED RECAP" not in result.message
        assert calls == ["fetch"]
        post.assert_not_called()

        steps = list_agent_plan_steps(
            db, tenant_id=str(tenant_a.id), plan_id=result.extra["plan_id"]
        )
        assert steps[0].status == "failed"
        assert steps[1].status == "skipped"
        assert steps[2].status == "skipped"


# ── Scenario 3: store a workflow, then run it later ──


class TestScenario3:
    """Store request → executor store tool writes workflow_templates,
    body steps not executed; later run request → orchestrator reads that
    row; executor runs planned tools only."""

    STORE_QUESTION = "Store this incident triage workflow in our shared library."
    BODY = "Post to #incidents, assign severity, notify on-call."
    STORE_STEPS = [
        {
            "tool_name": "store_workflow",
            "arguments": {"title": "Incident triage", "body_text": BODY, "filename": "triage.txt"},
            "success_criteria": "stored",
        },
    ]

    def test_yesterday_store_persists_without_running_body(
        self, db: Session, tenant_a: Tenant
    ):
        from api.app.db.plan_store import insert_tool_registry

        insert_tool_registry(
            db, tenant_id=str(tenant_a.id), name="store_workflow", kind="code"
        )
        db.commit()

        body_tools: dict[str, Any] = {
            "post_incidents": make_boom("must not run body"),
            "assign_severity": make_boom("must not run body"),
            "notify_oncall": make_boom("must not run body"),
        }
        result = run_facade(
            db, tenant_a, self.STORE_QUESTION, self.STORE_STEPS,
            tools=body_tools,
        )
        assert result.status == "succeeded"
        rows = list(
            db.scalars(
                select(WorkflowTemplate).where(WorkflowTemplate.tenant_id == tenant_a.id)
            ).all()
        )
        assert len(rows) == 1
        assert rows[0].title == "Incident triage"
        assert rows[0].body_text == self.BODY
        for spy in body_tools.values():
            spy.assert_not_called()

    def test_today_run_executes_only_planned_tools(
        self, db: Session, tenant_a: Tenant
    ):
        add_template(
            db, tenant_a, title="Incident triage",
            body="Post to #incidents, assign severity, notify on-call.",
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        RUN_STEPS = [
            {"tool_name": "post_incidents", "arguments": {"channel": "#incidents"}, "success_criteria": "posted"},
            {"tool_name": "assign_severity", "arguments": {}, "success_criteria": "assigned"},
            {"tool_name": "notify_oncall", "arguments": {}, "success_criteria": "notified"},
        ]
        calls: list[str] = []
        extra = make_boom("unlisted tool must not run")
        tools = {
            "post_incidents": lambda arguments: calls.append("post") or {"ok": True},
            "assign_severity": lambda arguments: calls.append("assign") or {"ok": True},
            "notify_oncall": lambda arguments: calls.append("notify") or {"ok": True},
            "store_workflow": extra,
            "create_powerpoint": extra,
        }
        result = run_facade(
            db, tenant_a,
            "Get me the workflow I defined and stored yesterday and get it to run immediately.",
            RUN_STEPS, tools=tools,
        )
        assert result.status == "succeeded"
        assert calls == ["post", "assign", "notify"]
        extra.assert_not_called()


# ── Scenario 4: run a named stored workflow with extra constraints ──


class TestScenario4:
    """Overrides skip laptop and change welcome channel; template body_text
    unchanged after run."""

    QUESTION = (
        "Run the onboarding workflow for the new hire starting Monday, "
        "but skip the laptop request and send the welcome note to #people "
        "instead of #general."
    )
    STEPS = [
        {"tool_name": "send_welcome_note", "arguments": {"channel": "#people"}, "success_criteria": "welcome posted"},
        {"tool_name": "add_to_payroll", "arguments": {"start": "Monday"}, "success_criteria": "payroll updated"},
    ]

    def test_laptop_skipped_welcome_to_people_template_unchanged(
        self, db: Session, tenant_a: Tenant
    ):
        body = (
            "1. Send a welcome note to #general.\n"
            "2. Request a laptop for the new hire.\n"
            "3. Add the hire to payroll."
        )
        template = add_template(db, tenant_a, title="Onboarding", body=body)
        original_body = template.body_text

        laptop = make_boom("laptop step must not run")
        posted: list[dict[str, Any]] = []
        tools = {
            "request_laptop": laptop,
            "send_welcome_note": lambda arguments: posted.append(dict(arguments)) or {"ok": True},
            "add_to_payroll": lambda arguments: {"ok": True},
        }
        result = run_facade(
            db, tenant_a, self.QUESTION, self.STEPS, tools=tools,
        )
        assert result.status == "succeeded"
        laptop.assert_not_called()
        assert posted and posted[0].get("channel") == "#people"

        db.refresh(template)
        assert template.body_text == original_body


# ── Scenario 5: mix of a stored workflow and a one-off follow-up ──


class TestScenario5:
    """Combined plan order = workflow steps then pdf/email; missing email
    tool → no claim that email was sent."""

    QUESTION = "Run the weekly status workflow, then email me a PDF of the result."
    STEPS = [
        {"tool_name": "gather_status", "arguments": {}, "success_criteria": "status collected"},
        {"tool_name": "compose_digest", "arguments": {}, "success_criteria": "digest written"},
        {"tool_name": "post_slack_message", "arguments": {"channel": "#status"}, "success_criteria": "posted"},
        {"tool_name": "generate_pdf", "arguments": {}, "success_criteria": "pdf rendered"},
        {"tool_name": "send_email", "arguments": {}, "success_criteria": "email sent"},
    ]

    def test_missing_pdf_stops_without_email(self, db: Session, tenant_a: Tenant):
        add_template(
            db, tenant_a, title="Weekly status",
            body="Gather team status, compose a digest, post the digest to #status.",
        )
        calls: list[str] = []
        email = make_boom("must not send email")
        tools = {
            "gather_status": lambda arguments: calls.append("gather") or {"ok": True},
            "compose_digest": lambda arguments: calls.append("compose") or {"ok": True},
            "post_slack_message": lambda arguments: calls.append("post") or {"ok": True},
            "send_email": email,
        }
        result = run_facade(
            db, tenant_a, self.QUESTION, self.STEPS, tools=tools,
        )
        assert result.status == "failed"
        assert "generate_pdf" in result.message
        assert "email was sent" not in result.message.lower()
        assert "sent" not in result.message.lower()
        assert calls == ["gather", "compose", "post"]
        email.assert_not_called()

        steps = list_agent_plan_steps(
            db, tenant_id=str(tenant_a.id), plan_id=result.extra["plan_id"]
        )
        assert [s.status for s in steps] == [
            "succeeded", "succeeded", "succeeded", "failed", "skipped",
        ]

    def test_all_tools_present_succeeds(self, db: Session, tenant_a: Tenant):
        add_template(
            db, tenant_a, title="Weekly status",
            body="Gather team status, compose a digest, post the digest to #status.",
        )
        calls: list[str] = []
        tools = {
            "gather_status": lambda arguments: calls.append("gather") or {"ok": True},
            "compose_digest": lambda arguments: calls.append("compose") or {"ok": True},
            "post_slack_message": lambda arguments: calls.append("post") or {"ok": True},
            "generate_pdf": lambda arguments: calls.append("pdf") or {"ok": True},
            "send_email": lambda arguments: calls.append("email") or {"ok": True},
        }
        result = run_facade(
            db, tenant_a, self.QUESTION, self.STEPS, tools=tools,
        )
        assert result.status == "succeeded"
        assert calls == ["gather", "compose", "post", "pdf", "email"]


# ── Isolation tests (Task 47.3) ──


class TestIsolation:
    """Tenant B cannot execute tenant A's plan; orchestrator gather cannot
    attach tenant B's workflow document to tenant A's plan."""

    def test_executor_refuses_cross_tenant_plan(
        self, db: Session, tenant_a: Tenant, tenant_b: Tenant
    ):
        steps_a = [
            {"tool_name": "post_slack_message", "arguments": {"channel": "#secret"}, "success_criteria": "posted"},
        ]
        result_a = run_facade(
            db, tenant_a, "Post to #secret", steps_a,
            tools={"post_slack_message": make_spy("post")},
        )
        assert result_a.status == "succeeded"
        plan_id_a = result_a.extra["plan_id"]

        from api.app.agent.base import AgentContext
        from api.app.agent.factory import get_agent

        executor = get_agent("executor")
        exec_result = executor.run(
            AgentContext(
                client_id=str(tenant_b.id),
                extra={"db": db, "plan_id": plan_id_a, "tools": {"post_slack_message": make_spy()}},
            )
        )
        assert exec_result.status == "failed"
        assert "not found" in exec_result.message

    def test_orchestrator_cannot_read_other_tenant_workflow(
        self, db: Session, tenant_a: Tenant, tenant_b: Tenant
    ):
        secret = "TENANT B SECRET BODY — never attach to A"
        add_template(db, tenant_b, title="Onboarding", body=secret)

        result = run_facade(
            db, tenant_a,
            "Run the onboarding workflow for the new hire.",
            None,
        )
        assert result.status == "failed"
        plan_id = result.extra["plan_id"]

        plan = get_agent_plan(db, tenant_id=str(tenant_a.id), plan_id=plan_id)
        assert plan is not None
        assert secret not in str(plan.source)
        assert secret not in str(plan.plan_json)

        assert list_agent_plans(db, tenant_id=str(tenant_b.id)) == []


# ── Tool RAG behaviour (complaints-of-feature.Md System Behaviour Test) ──


class TestToolRagSystemBehaviour:
    """Maps 1:1 to the Tool RAG System Behaviour Test section.

    English-goal planning without tool-registry shortlist injection.
    """

    def test_planner_uses_english_goals_without_tool_catalog(
        self, db: Session, tenant_a: Tenant
    ):
        from api.app.agent.base import AgentContext
        from api.app.agent.factory import get_agent
        from api.app.agent.llm import StubChatModel
        from api.app.db.tool_store import insert_tool_registry

        # Registry noise must not be injected into the planner prompt.
        for i in range(30):
            insert_tool_registry(
                db,
                tenant_id=str(tenant_a.id),
                name=f"noise_tool_{i:02d}",
                kind="code",
                description=f"Unrelated utility {i}",
                config={"subcommands": {f"sub_{i}": {"purpose": "noise"}}},
            )
        db.commit()

        steps = [
            {
                "tool_name": "execute_goal",
                "arguments": {
                    "instruction": "Create a 3 page financial report pptx from the excel file"
                },
                "success_criteria": "pptx exists",
            },
        ]
        recorded: list[str] = []

        class _Recording:
            def complete(self, **kwargs: Any) -> Any:
                for msg in kwargs.get("messages") or []:
                    if msg.get("role") == "user":
                        recorded.append(str(msg.get("content") or ""))
                return StubChatModel(scripted_text={"steps": steps}).complete(**kwargs)

        result = get_agent("orchestrator").run(
            AgentContext(
                client_id=str(tenant_a.id),
                question=(
                    "Create a 3 page financial report pptx from the excel file "
                    "I just uploaded here in Slack."
                ),
                attachments=[
                    {
                        "filename": "finance.xlsx",
                        "mimetype": "application/vnd.ms-excel",
                        "file_id": "F123EXCEL",
                    }
                ],
                extra={
                    "db": db,
                    "chat_model": _Recording(),
                    "settings": type(
                        "S",
                        (),
                        {
                            "orchestrator_max_tokens": 4096,
                            "tool_rag_top_k": 8,
                            "tool_rag_use_embeddings": False,
                            "tool_rag_workflow_body_chars": 1500,
                        },
                    )(),
                },
            )
        )
        assert result.status == "ready"
        assert recorded, "orchestrator must send a planner prompt"
        prompt = recorded[0]
        assert "Shortlisted tool catalog" not in prompt
        assert "noise_tool_" not in prompt
        assert "execute_goal" in prompt
        plan_id = result.extra["plan_id"]
        plan_steps = list_agent_plan_steps(
            db, tenant_id=str(tenant_a.id), plan_id=plan_id
        )
        assert [s.tool_name for s in plan_steps] == ["execute_goal"]

    def test_executor_lazy_loads_full_schema_after_plan(
        self, db: Session, tenant_a: Tenant
    ):
        from api.app.agent.tool_rag import load_full_tool_schema
        from api.app.agent.tools import DbToolDiscovery
        from api.app.db.tool_store import insert_tool_registry

        insert_tool_registry(
            db,
            tenant_id=str(tenant_a.id),
            name="create_powerpoint",
            kind="code",
            description="Create pptx",
            config={"subcommands": {"build": {"purpose": "render"}}},
        )
        db.commit()

        result = run_facade(
            db,
            tenant_a,
            "Create a powerpoint",
            [
                {
                    "tool_name": "create_powerpoint",
                    "arguments": {"pages": 1},
                    "success_criteria": "pptx",
                }
            ],
            tools={
                "create_powerpoint": lambda arguments: {"ok": True, "pages": arguments.get("pages")},
            },
        )
        assert result.status == "succeeded"

        discovery = DbToolDiscovery(db, {"tools": {}})
        ref = discovery.find("create_powerpoint", client_id=str(tenant_a.id))
        assert ref is not None
        full = load_full_tool_schema(ref)
        assert full["subcommands"]["build"]["purpose"] == "render"

    def test_large_workflow_body_is_summarized_in_planner_prompt(
        self, db: Session, tenant_a: Tenant
    ):
        from api.app.agent.base import AgentContext
        from api.app.agent.factory import get_agent
        from api.app.agent.llm import StubChatModel

        long_noise = ("filler paragraph about unrelated archive policy. " * 80)
        body = (
            "1. Gather team status.\n"
            "2. Compose digest.\n"
            "3. Post to #status.\n"
            f"{long_noise}\n"
            "4. Email a PDF of the result.\n"
        )
        add_template(db, tenant_a, title="Weekly status", body=body)

        recorded: list[str] = []

        class _Recording:
            def complete(self, **kwargs: Any) -> Any:
                for msg in kwargs.get("messages") or []:
                    if msg.get("role") == "user":
                        recorded.append(str(msg.get("content") or ""))
                return StubChatModel(
                    scripted_text={
                        "steps": [
                            {
                                "tool_name": "gather_status",
                                "arguments": {},
                                "success_criteria": "ok",
                            }
                        ]
                    }
                ).complete(**kwargs)

        get_agent("orchestrator").run(
            AgentContext(
                client_id=str(tenant_a.id),
                question="Run the weekly status workflow, then email me a PDF of the result.",
                extra={
                    "db": db,
                    "chat_model": _Recording(),
                    "tools": {"gather_status": lambda arguments: {"ok": True}},
                    "settings": type(
                        "S",
                        (),
                        {
                            "orchestrator_max_tokens": 4096,
                            "tool_rag_top_k": 8,
                            "tool_rag_use_embeddings": False,
                            "tool_rag_workflow_body_chars": 400,
                        },
                    )(),
                },
            )
        )
        assert recorded
        prompt = recorded[0]
        assert "Weekly status" in prompt or "weekly status" in prompt.lower()
        assert long_noise not in prompt
        assert len(prompt) < len(body) + 2000
