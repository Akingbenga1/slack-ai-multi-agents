"""Targeted tests for potential issues in Orchestrator + Executor agents.

Tests here avoid DB fixtures — they validate logic paths at the unit level.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from api.app.agent.base import AgentContext, AgentResult
from api.app.agent.llm import LlmResult, StubChatModel
from api.app.agent.orchestrator import parse_plan, parse_plan_steps
from api.app.agent.tools import (
    ToolExecutionError,
    ToolRef,
    invoke_tool,
    lookup_tool,
    result_error,
)


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE 1: LLM returns malformed / non-JSON — orchestrator parse resilience
# ═══════════════════════════════════════════════════════════════════════════════


class TestParsePlanResilience:
    """Verify parse_plan handles bad LLM output gracefully."""

    def test_empty_string_returns_qa_no_steps(self):
        wf, steps = parse_plan("")
        assert wf == "qa"
        assert steps == []

    def test_none_returns_qa_no_steps(self):
        wf, steps = parse_plan(None)
        assert wf == "qa"
        assert steps == []

    def test_plain_english_no_json(self):
        wf, steps = parse_plan(
            "I think you should summarize the channel and then post it."
        )
        assert steps == []

    def test_json_with_markdown_prose_around_it(self):
        raw = (
            "Here's my plan:\n\n"
            "```json\n"
            '{"workflow": "summarize", "steps": [{"tool_name": "fetch", "arguments": {}}]}\n'
            "```\n\n"
            "Let me know if you want changes."
        )
        wf, steps = parse_plan(raw)
        assert wf == "summarize"
        assert len(steps) == 1
        assert steps[0]["tool_name"] == "fetch"

    def test_json_missing_tool_name_skips_step(self):
        raw = json.dumps(
            {"steps": [{"arguments": {"x": 1}}, {"tool_name": "ok", "arguments": {}}]}
        )
        wf, steps = parse_plan(raw)
        assert len(steps) == 1
        assert steps[0]["tool_name"] == "ok"

    def test_partial_json_truncated(self):
        raw = '{"workflow": "report", "steps": [{"tool_name": "gather", "arguments": {'
        wf, steps = parse_plan(raw)
        assert steps == []

    def test_json_array_instead_of_object(self):
        raw = json.dumps([{"tool_name": "a", "arguments": {}}, {"tool_name": "b", "arguments": {}}])
        wf, steps = parse_plan(raw)
        assert wf == "qa"
        assert len(steps) == 2

    def test_invalid_workflow_field_defaults_to_qa(self):
        raw = json.dumps({"workflow": "", "steps": [{"tool_name": "x", "arguments": {}}]})
        wf, steps = parse_plan(raw)
        assert wf == "qa"

    def test_non_dict_step_items_skipped(self):
        raw = json.dumps({"steps": ["not a dict", 42, {"tool_name": "real", "arguments": {}}]})
        _, steps = parse_plan(raw)
        assert len(steps) == 1
        assert steps[0]["tool_name"] == "real"


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE 2: LLM call raises an exception — orchestrator doesn't catch it
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrchestratorLlmException:
    """The orchestrator has no try/except around model.complete().
    Verify the exception propagates (confirming the issue exists)."""

    def test_llm_exception_propagates_uncaught(self):
        class ExplodingModel:
            def complete(self, **kwargs):
                raise RuntimeError("API timeout")

        from api.app.agent.orchestrator import OrchestratorAgent

        agent = OrchestratorAgent()
        ctx = AgentContext(
            client_id=str(uuid4()),
            question="Summarize #general",
            extra={
                "chat_model": ExplodingModel(),
                "db": MagicMock(),
            },
        )
        with pytest.raises(RuntimeError, match="API timeout"):
            agent.run(ctx)


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE 3: Executor — tool in plan but not registered → fails step
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecutorToolNotFound:
    """If the orchestrator plans a tool that isn't registered, executor fails."""

    def test_lookup_returns_none_for_unknown_tool(self):
        db = MagicMock()
        db.scalar.return_value = None
        db.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))

        ref = lookup_tool("generate_pdf", client_id=str(uuid4()), db=db, extra={})
        assert ref is None

    def test_lookup_finds_injected_tool(self):
        fn = lambda **kw: {"ok": True}
        ref = lookup_tool(
            "generate_pdf",
            client_id=str(uuid4()),
            db=MagicMock(),
            extra={"tools": {"generate_pdf": fn}},
        )
        assert ref is not None
        assert ref.source == "injected"
        assert ref.invoke is fn


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE 4: invoke_tool — registry tool with no handler raises ToolExecutionError
# ═══════════════════════════════════════════════════════════════════════════════


class TestInvokeToolNoHandler:
    """A ToolRef from registry with no invoke, not a store name, not MCP."""

    def test_registry_tool_no_handler_raises(self):
        ref = ToolRef(name="mystery_tool", source="registry", kind="code", invoke=None)
        db = MagicMock()
        with pytest.raises(ToolExecutionError, match="no handler"):
            invoke_tool(ref, {}, client_id=str(uuid4()), db=db)

    def test_mcp_tool_with_injected_call(self):
        called = {}

        def mock_mcp(name, args):
            called["name"] = name
            called["args"] = args
            return {"ok": True, "data": "hello"}

        ref = ToolRef(name="slack_search", source="mcp", kind="mcp", invoke=None)
        result = invoke_tool(
            ref,
            {"query": "test"},
            client_id=str(uuid4()),
            db=MagicMock(),
            extra={"call_mcp_tool": mock_mcp},
        )
        assert result["ok"] is True
        assert called["name"] == "slack_search"

    def test_search_knowledge_code_handler_runs(self):
        from api.app.retrieval.types import KnowledgeCitation, KnowledgeSearchResult

        cid = str(uuid4())
        ref = ToolRef(
            name="search_knowledge",
            source="registry",
            kind="code",
            invoke=None,
        )
        result_obj = KnowledgeSearchResult(
            client_id=cid,
            query="refund policy",
            hits=[
                KnowledgeCitation(
                    point_id="1",
                    score=0.9,
                    text="Refunds within 30 days.",
                    kind="document",
                    client_id=cid,
                    filename="policy.md",
                )
            ],
            limit=8,
        )
        with patch(
            "api.app.retrieval.search_knowledge",
            return_value=result_obj,
        ) as search_mock:
            out = invoke_tool(
                ref,
                {"query": "refund policy"},
                client_id=cid,
                db=MagicMock(),
            )
        assert out["ok"] is True
        assert out["hit_count"] == 1
        assert out["hits"][0]["text"] == "Refunds within 30 days."
        search_mock.assert_called_once()
        assert search_mock.call_args.kwargs["client_id"] == cid
        assert search_mock.call_args.kwargs["query"] == "refund policy"


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE 5: result_error — verifying it catches failure signals
# ═══════════════════════════════════════════════════════════════════════════════


class TestResultError:
    def test_ok_false_is_error(self):
        assert result_error({"ok": False, "error": "boom"}) == "boom"

    def test_success_false_is_error(self):
        assert result_error({"success": False}) == "tool returned success=false"

    def test_ok_true_is_not_error(self):
        assert result_error({"ok": True, "data": "x"}) is None

    def test_non_dict_is_not_error(self):
        assert result_error("string result") is None
        assert result_error(None) is None


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE 6: Orchestrator plans tools freely but executor can't find them
# End-to-end demonstration (mocked DB)
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrchestratorExecutorMismatch:
    """Demonstrates the core gap: orchestrator plans unregistered tools,
    executor fails because those tools don't exist."""

    def test_planned_tool_not_in_registry_causes_executor_failure(self):
        from api.app.agent.executor import ExecutorAgent

        plan_id = uuid4()
        tenant_id = str(uuid4())

        mock_plan = MagicMock()
        mock_plan.id = plan_id
        mock_plan.status = "ready"

        mock_step = MagicMock()
        mock_step.tool_name = "generate_pdf"
        mock_step.arguments = {}
        mock_step.step_index = 0
        mock_step.status = "pending"
        mock_step.error = None
        mock_step.result = None

        mock_run = MagicMock()
        mock_run.id = uuid4()
        mock_run.status = "pending"

        db = MagicMock()
        db.scalar.return_value = None
        db.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))

        from api.app.agent.llm import LlmResult, ToolCall

        class _StubExecModel:
            def complete(self, **kw: Any) -> LlmResult:
                return LlmResult(
                    text="", model="stub", input_tokens=1, output_tokens=1,
                    tool_calls=(ToolCall(name="generate_pdf", arguments={}, id="c"),),
                )

        with patch("api.app.agent.executor.get_agent_plan", return_value=mock_plan), \
             patch("api.app.agent.executor.insert_agent_run", return_value=mock_run), \
             patch("api.app.agent.executor.list_agent_plan_steps", return_value=[mock_step]):

            agent = ExecutorAgent()
            result = agent.run(
                AgentContext(
                    client_id=tenant_id,
                    question="make a pdf",
                    extra={"db": db, "plan_id": str(plan_id), "tools": {}, "chat_model": _StubExecModel()},
                )
            )

        assert result.status == "failed"
        assert "generate_pdf" in (mock_step.error or "")
