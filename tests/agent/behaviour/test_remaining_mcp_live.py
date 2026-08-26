"""Live system behaviour tests from remaining_mcp.md against public no-auth MCP servers.

Repeats behaviours 1–4 for three Streamable HTTP servers that require no API key.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from api.app.agent.base import AgentContext
from api.app.agent.factory import get_agent
from api.app.agent.mcp_host import check_mcp_server
from api.app.db.models import Tenant
from api.app.db.plan_store import (
    insert_agent_plan,
    insert_agent_plan_step,
    list_agent_plan_steps,
)
from api.app.db.tool_store import insert_mcp_server, insert_tool_registry, update_mcp_server

# Three public HTTP MCP servers verified without authentication (beyond AI SENSE).
LIVE_NO_AUTH_SERVERS: list[dict[str, Any]] = [
    {
        "id": "merlonix",
        "server_name": "merlonix-public",
        "url": "https://api.merlonix.com/mcp",
        "tool_name": "check_mcp_health",
        "arguments": {"url": "https://aisenseapi.com/mcp"},
        "expect_substring": "reachable",
    },
    {
        "id": "turva",
        "server_name": "turva-public",
        "url": "https://mcp.turva.dev/mcp",
        "tool_name": "get_services",
        "arguments": {},
        "expect_substring": "pricing",
    },
    {
        "id": "gutenberg",
        "server_name": "gutenberg-public",
        "url": "https://gutenberg.caseyjhand.com/mcp",
        "tool_name": "gutenberg_browse_popular",
        "arguments": {},
        "expect_substring": "Moby",
    },
]


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


def _register(db: Session, tenant: Tenant, spec: dict[str, Any], *, enabled: bool = True):
    server = insert_mcp_server(
        db,
        tenant_id=str(tenant.id),
        name=spec["server_name"],
        transport="http",
        connection_config={"url": spec["url"]},
        enabled=enabled,
    )
    insert_tool_registry(
        db,
        tenant_id=str(tenant.id),
        name=spec["tool_name"],
        kind="mcp",
        mcp_server_id=server.id,
        description=f"Live no-auth MCP tool from {spec['id']}",
    )
    db.commit()
    return server


@pytest.mark.parametrize("spec", LIVE_NO_AUTH_SERVERS, ids=lambda s: s["id"])
class TestLiveRemainingMcpBehaviours:
    """remaining_mcp.md behaviours 1–4 against live no-auth HTTP MCPs."""

    def test_1_slack_ask_uses_registry_mcp_and_returns_content(
        self, db: Session, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch, spec: dict
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

        _register(db, tenant_a, spec)
        plan = _seed_ready_plan(
            db,
            tenant_a,
            question=f"@bot use {spec['tool_name']} from {spec['id']} MCP",
            steps=[
                {
                    "tool_name": spec["tool_name"],
                    "arguments": dict(spec["arguments"]),
                }
            ],
        )
        result = get_agent("executor").run(
            AgentContext(
                client_id=str(tenant_a.id),
                question=plan.question,
                extra={"db": db, "plan_id": str(plan.id)},
            )
        )
        assert result.status == "succeeded", result.message
        assert spec["expect_substring"].lower() in result.message.lower()
        bundled.assert_not_called()
        stored = list_agent_plan_steps(
            db, tenant_id=str(tenant_a.id), plan_id=plan.id
        )
        assert stored[0].status == "succeeded"
        assert stored[0].result

    def test_2_http_mcp_ready_uses_connection_config_never_bundled(
        self, db: Session, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch, spec: dict
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

        server = _register(db, tenant_a, spec)
        check = check_mcp_server(
            server_name=server.name,
            transport=server.transport,
            connection_config=server.connection_config
            if isinstance(server.connection_config, dict)
            else {},
            enabled=True,
            timeout_seconds=30.0,
        )
        assert check.ready is True, check.error
        assert check.tool_count and check.tool_count > 0
        assert spec["tool_name"] in (check.tool_names or [])

        plan = _seed_ready_plan(
            db,
            tenant_a,
            question=f"Use ready HTTP MCP {spec['id']}",
            steps=[
                {
                    "tool_name": spec["tool_name"],
                    "arguments": dict(spec["arguments"]),
                }
            ],
        )
        result = get_agent("executor").run(
            AgentContext(
                client_id=str(tenant_a.id),
                extra={"db": db, "plan_id": str(plan.id)},
            )
        )
        assert result.status == "succeeded", result.message
        assert spec["expect_substring"].lower() in result.message.lower()
        bundled.assert_not_called()

    def test_3_disabled_server_skips_without_bundled_fallback(
        self, db: Session, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch, spec: dict
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

        server = _register(db, tenant_a, spec)
        update_mcp_server(
            db, tenant_id=str(tenant_a.id), name=server.name, enabled=False
        )
        db.commit()

        later_calls: list[str] = []

        def compose(arguments: dict[str, Any]):
            later_calls.append("compose")
            return {"ok": True, "text": "composed after skip"}

        insert_tool_registry(
            db,
            tenant_id=str(tenant_a.id),
            name="compose_summary",
            kind="code",
        )
        db.commit()

        plan = _seed_ready_plan(
            db,
            tenant_a,
            question="Lookup then summarise",
            steps=[
                {
                    "tool_name": spec["tool_name"],
                    "arguments": dict(spec["arguments"]),
                },
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

    def test_4_multi_step_later_reads_mcp_payload(
        self, db: Session, tenant_a: Tenant, monkeypatch: pytest.MonkeyPatch, spec: dict
    ):
        bundled = MagicMock(
            side_effect=AssertionError("must not call bundled mcp_client")
        )
        monkeypatch.setattr(
            "api.app.agent.mcp_client.call_mcp_tool", bundled, raising=False
        )

        _register(db, tenant_a, spec)
        insert_tool_registry(
            db, tenant_id=str(tenant_a.id), name="prep_context", kind="code"
        )
        insert_tool_registry(
            db, tenant_id=str(tenant_a.id), name="compose_answer", kind="code"
        )
        db.commit()

        def compose(arguments: dict[str, Any]):
            prior = arguments.get("prior_step_results") or {}
            mcp_payload = prior.get(spec["tool_name"]) or {}
            blob = str(mcp_payload)
            assert spec["expect_substring"].lower() in blob.lower()
            return {
                "ok": True,
                "text": f"Final answer uses MCP from {spec['id']}",
            }

        plan = _seed_ready_plan(
            db,
            tenant_a,
            question=f"Prep, call {spec['tool_name']}, then answer",
            steps=[
                {"tool_name": "prep_context", "arguments": {}},
                {
                    "tool_name": spec["tool_name"],
                    "arguments": dict(spec["arguments"]),
                },
                {"tool_name": "compose_answer", "arguments": {}},
            ],
        )
        result = get_agent("executor").run(
            AgentContext(
                client_id=str(tenant_a.id),
                extra={
                    "db": db,
                    "plan_id": str(plan.id),
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
        assert result.status == "succeeded", result.message
        assert spec["expect_substring"].lower() in result.message.lower()
        assert f"Final answer uses MCP from {spec['id']}" in result.message
        bundled.assert_not_called()
        steps = list_agent_plan_steps(
            db, tenant_id=str(tenant_a.id), plan_id=plan.id
        )
        assert [s.status for s in steps] == ["succeeded", "succeeded", "succeeded"]
        assert steps[1].result
