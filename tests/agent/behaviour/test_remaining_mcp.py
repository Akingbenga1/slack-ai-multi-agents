"""System behaviour tests from remaining_mcp.md (registry MCP → executor)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from api.app.agent.base import AgentContext
from api.app.agent.factory import get_agent
from api.app.db.models import McpServer, Tenant
from api.app.db.plan_store import (
    insert_agent_plan,
    insert_agent_plan_step,
    list_agent_plan_steps,
)
from api.app.db.tool_store import insert_mcp_server, insert_tool_registry, update_mcp_server

def _seed_ready_plan(
    db: Session,
    tenant: Tenant,
    *,
    question: str,
    steps: list[dict[str, Any]],
):
    plan = insert_agent_plan(
        db,
        tenant_id=str(tenant.id),
        question=question,
        status="ready",
        plan_json={"steps": steps},
    )
    for index, step in enumerate(steps):
        insert_agent_plan_step(
            db,
            tenant_id=str(tenant.id),
            plan_id=plan.id,
            step_index=index,
            tool_name=str(step.get("tool_name") or ""),
            arguments=dict(step.get("arguments") or {}),
            status="pending",
        )
    db.commit()
    return plan


def _register_http_mcp_tool(
    db: Session,
    tenant: Tenant,
    *,
    server_name: str = "ext-http",
    tool_name: str = "external_lookup",
    url: str = "https://mcp.example.test/mcp",
    enabled: bool = True,
) -> McpServer:
    server = insert_mcp_server(
        db,
        tenant_id=str(tenant.id),
        name=server_name,
        transport="http",
        connection_config={"url": url},
        enabled=enabled,
    )
    insert_tool_registry(
        db,
        tenant_id=str(tenant.id),
        name=tool_name,
        kind="mcp",
        mcp_server_id=server.id,
        description="Registered external MCP tool",
    )
    db.commit()
    return server


class TestRemainingMcpBehaviour1:
    """Slack ask needing an external MCP tool."""

    def test_slack_mention_uses_registry_mcp_and_returns_content(
        self, db: Session, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
    ):
        bundled = MagicMock(
            side_effect=AssertionError("must not call bundled mcp_client")
        )
        monkeypatch.setattr(
            "api.app.agent.mcp_client.call_mcp_tool", bundled, raising=False
        )

        server = _register_http_mcp_tool(db, tenant_a)
        seen: list[Any] = []

        def fake_call(name: str, arguments: dict[str, Any], mcp_server: Any = None):
            seen.append((name, arguments, mcp_server))
            assert name == "external_lookup"
            assert mcp_server is not None
            assert mcp_server.id == server.id
            assert mcp_server.connection_config == {
                "url": "https://mcp.example.test/mcp"
            }
            return {"ok": True, "text": "EXTERNAL_MCP_HIT: refund window is 30 days"}

        steps = [
            {
                "tool_name": "external_lookup",
                "arguments": {"query": "refund policy"},
                "success_criteria": "lookup done",
            },
        ]
        plan = _seed_ready_plan(
            db,
            tenant_a,
            question="@bot what is our refund policy from the finance MCP?",
            steps=steps,
        )
        exec_result = get_agent("executor").run(
            AgentContext(
                client_id=str(tenant_a.id),
                question=plan.question,
                extra={
                    "db": db,
                    "plan_id": str(plan.id),
                    "call_mcp_tool": fake_call,
                },
            )
        )
        assert exec_result.status == "succeeded"
        assert "EXTERNAL_MCP_HIT" in exec_result.message
        assert "30 days" in exec_result.message
        assert seen and seen[0][0] == "external_lookup"
        bundled.assert_not_called()

        stored = list_agent_plan_steps(
            db, tenant_id=str(tenant_a.id), plan_id=plan.id
        )
        assert stored[0].status == "succeeded"
        assert stored[0].result and "EXTERNAL_MCP_HIT" in str(stored[0].result)


class TestRemainingMcpBehaviour2:
    """Registered HTTP MCP marked ready — agent uses connection_config, not bundled."""

    def test_http_mcp_from_connection_config_never_bundled(
        self, db: Session, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
    ):
        bundled = MagicMock(
            side_effect=AssertionError("must not call bundled mcp_client")
        )
        monkeypatch.setattr(
            "api.app.agent.mcp_client.call_mcp_tool", bundled, raising=False
        )
        monkeypatch.setattr(
            "api.app.agent.mcp_client.call_mcp_tool_async",
            bundled,
            raising=False,
        )

        server = _register_http_mcp_tool(
            db,
            tenant_a,
            url="https://ready.example.test/mcp",
        )
        opened: list[dict[str, Any]] = []

        def fake_registered(**kwargs: Any):
            opened.append(dict(kwargs))
            assert kwargs["server_name"] == server.name
            assert kwargs["transport"] == "http"
            assert kwargs["connection_config"] == {
                "url": "https://ready.example.test/mcp"
            }
            assert kwargs["tool_name"] == "external_lookup"
            return {"ok": True, "text": "from-live-http-session"}

        monkeypatch.setattr(
            "api.app.agent.mcp_host.call_registered_mcp_tool",
            fake_registered,
        )

        plan = _seed_ready_plan(
            db,
            tenant_a,
            question="Use the ready HTTP MCP tool",
            steps=[
                {
                    "tool_name": "external_lookup",
                    "arguments": {"query": "x"},
                }
            ],
        )
        result = get_agent("executor").run(
            AgentContext(
                client_id=str(tenant_a.id),
                extra={"db": db, "plan_id": str(plan.id)},
            )
        )
        assert result.status == "succeeded"
        assert "from-live-http-session" in result.message
        assert opened and opened[0]["connection_config"]["url"].startswith("https://")
        bundled.assert_not_called()


class TestRemainingMcpBehaviour3:
    """Tenant disables an MCP server — soft skip, no bundled fallback."""

    def test_disabled_server_skips_without_bundled_fallback(
        self, db: Session, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
    ):
        bundled = MagicMock(
            side_effect=AssertionError("must not call bundled mcp_client")
        )
        monkeypatch.setattr(
            "api.app.agent.mcp_client.call_mcp_tool", bundled, raising=False
        )
        live = MagicMock(
            side_effect=AssertionError("must not open live MCP when disabled")
        )
        monkeypatch.setattr(
            "api.app.agent.mcp_host.call_registered_mcp_tool", live
        )

        server = _register_http_mcp_tool(db, tenant_a)
        update_mcp_server(
            db, tenant_id=str(tenant_a.id), name=server.name, enabled=False
        )
        db.commit()

        later_calls: list[str] = []

        def compose(arguments: dict[str, Any]):
            later_calls.append("compose")
            prior = arguments.get("prior_step_results") or {}
            return {
                "ok": True,
                "text": f"composed without mcp prior={bool(prior)}",
            }

        insert_tool_registry(
            db, tenant_id=str(tenant_a.id), name="compose_summary", kind="code"
        )
        db.commit()

        plan = _seed_ready_plan(
            db,
            tenant_a,
            question="Lookup then summarise",
            steps=[
                {"tool_name": "external_lookup", "arguments": {"query": "x"}},
                {"tool_name": "compose_summary", "arguments": {}},
            ],
        )
        result = get_agent("executor").run(
            AgentContext(
                client_id=str(tenant_a.id),
                extra={
                    "db": db,
                    "plan_id": str(plan.id),
                    "tools": {"compose_summary": compose},
                },
            )
        )
        assert result.status == "succeeded"
        assert "unavailable" in result.message.lower()
        assert later_calls == ["compose"]
        bundled.assert_not_called()
        live.assert_not_called()

        steps = list_agent_plan_steps(
            db, tenant_id=str(tenant_a.id), plan_id=plan.id
        )
        assert steps[0].status == "skipped"
        assert steps[0].result and steps[0].result.get("unavailable") is True
        assert steps[1].status == "succeeded"


class TestRemainingMcpBehaviour4:
    """Multi-step plan with MCP in the middle — later steps read stored payload."""

    def test_later_step_reads_mcp_payload(
        self, db: Session, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch
    ):
        bundled = MagicMock(
            side_effect=AssertionError("must not call bundled mcp_client")
        )
        monkeypatch.setattr(
            "api.app.agent.mcp_client.call_mcp_tool", bundled, raising=False
        )
        _register_http_mcp_tool(db, tenant_a, tool_name="fetch_metrics")

        def mcp_call(name: str, arguments: dict[str, Any], mcp_server: Any = None):
            assert name == "fetch_metrics"
            assert mcp_server is not None
            return {"ok": True, "text": "METRIC=42", "metric": 42}

        def compose(arguments: dict[str, Any]):
            prior = arguments.get("prior_step_results") or {}
            mcp_payload = prior.get("fetch_metrics") or {}
            metric = mcp_payload.get("metric")
            return {
                "ok": True,
                "text": f"Final answer uses MCP metric={metric}",
            }

        insert_tool_registry(
            db, tenant_id=str(tenant_a.id), name="compose_answer", kind="code"
        )
        insert_tool_registry(
            db, tenant_id=str(tenant_a.id), name="prep_context", kind="code"
        )
        db.commit()

        plan = _seed_ready_plan(
            db,
            tenant_a,
            question="Prep, fetch MCP metrics, then answer",
            steps=[
                {"tool_name": "prep_context", "arguments": {}},
                {"tool_name": "fetch_metrics", "arguments": {"window": "week"}},
                {"tool_name": "compose_answer", "arguments": {}},
            ],
        )
        result = get_agent("executor").run(
            AgentContext(
                client_id=str(tenant_a.id),
                extra={
                    "db": db,
                    "plan_id": str(plan.id),
                    "call_mcp_tool": mcp_call,
                    "tools": {
                        "prep_context": lambda arguments: {
                            "ok": True,
                            "text": "prep-done",
                        },
                        "compose_answer": compose,
                    },
                },
            )
        )
        assert result.status == "succeeded"
        assert "METRIC=42" in result.message
        assert "Final answer uses MCP metric=42" in result.message
        bundled.assert_not_called()

        steps = list_agent_plan_steps(
            db, tenant_id=str(tenant_a.id), plan_id=plan.id
        )
        assert [s.status for s in steps] == ["succeeded", "succeeded", "succeeded"]
        assert steps[1].result and steps[1].result.get("metric") == 42
