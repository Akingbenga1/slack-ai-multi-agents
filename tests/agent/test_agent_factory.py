"""Agent role factory + contract (Sprint 42)."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from api.app.agent.base import Agent, AgentContext, AgentResult
from api.app.agent.executor import ExecutorAgent
from api.app.agent.factory import get_agent
from api.app.agent.guardrails import TenantContextRequired
from api.app.agent.orchestrator import OrchestratorAgent
from api.app.settings import Settings

_REPO = Path(__file__).resolve().parents[2]
_APP = _REPO / "api" / "app"
_TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

_CONCRETE_AGENTS = ("OrchestratorAgent", "ExecutorAgent")
_PRODUCT_NO_CONCRETE = (
    _APP / "agent" / "run.py",
    _APP / "slack" / "agent_reply.py",
    _APP / "slack" / "reply_pipeline.py",
    _APP / "slack" / "delivery",
)


def _iter_py(paths: tuple[Path, ...]):
    for p in paths:
        if p.is_file():
            yield p
        elif p.is_dir():
            yield from p.rglob("*.py")


def test_factory_returns_orchestrator_by_role():
    agent = get_agent("orchestrator")
    assert agent.role == "orchestrator"
    assert isinstance(agent, OrchestratorAgent)


def test_factory_returns_executor_by_role():
    agent = get_agent("executor")
    assert agent.role == "executor"
    assert isinstance(agent, ExecutorAgent)
    result = agent.run(AgentContext(client_id=_TENANT, question="run it"))
    assert result.role == "executor"
    assert result.status == "failed"
    assert "plan_id" in result.message


def test_factory_unknown_role_raises():
    with pytest.raises(ValueError, match="Unknown agent role"):
        get_agent("reviewer")


def test_base_helper_rejects_empty_client_id():
    agent = get_agent("orchestrator")
    with pytest.raises(TenantContextRequired):
        agent.run(AgentContext(client_id=""))
    with pytest.raises(TenantContextRequired):
        agent.run(AgentContext(client_id="  "))
    with pytest.raises(TenantContextRequired):
        agent.run(AgentContext(client_id=None))  # type: ignore[arg-type]


def test_executor_without_plan_id_does_not_call_mcp_or_chatmodel(monkeypatch):
    boom = MagicMock(side_effect=AssertionError("missing plan_id must not call I/O"))
    monkeypatch.setattr("api.app.agent.mcp_client.call_mcp_tool", boom, raising=False)
    monkeypatch.setattr("api.app.agent.llm.StubChatModel.complete", boom, raising=False)
    monkeypatch.setattr("api.app.agent.llm.get_chat_model", boom, raising=False)

    result = get_agent("executor").run(AgentContext(client_id=_TENANT, question="x"))
    assert result.status == "failed"
    boom.assert_not_called()


def test_executor_and_base_do_not_import_mcp_slack():
    forbidden = ("mcp_client", "slack")
    for name in ("executor.py", "base.py"):
        text = (_APP / "agent" / name).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{name} mentions {token!r}"
    base_text = (_APP / "agent" / "base.py").read_text(encoding="utf-8")
    for token in ("ChatModel", "get_chat_model"):
        assert token not in base_text, f"base.py mentions {token!r}"


def test_orchestrator_does_not_import_classifier_or_work_tools():
    text = (_APP / "agent" / "orchestrator.py").read_text(encoding="utf-8")
    for token in (
        "classify_workflow",
        "CLASSIFIER_RULES",
        "mcp_client",
        "copy_template",
        "update_personal_draft",
        "store_from_attached_evidence",
        "chat.postMessage",
        "ExecutorAgent",
    ):
        assert token not in text, f"orchestrator.py mentions {token!r}"


def test_usage_hook_optional():
    calls: list[tuple[AgentContext, AgentResult]] = []

    def hook(ctx: AgentContext, result: AgentResult) -> None:
        calls.append((ctx, result))

    skipped = get_agent("executor").run(
        AgentContext(client_id=_TENANT, record_usage=True, usage_hook=None)
    )
    assert skipped.status == "failed"
    assert calls == []

    recorded = get_agent("executor").run(
        AgentContext(client_id=_TENANT, record_usage=True, usage_hook=hook)
    )
    assert len(calls) == 1
    assert calls[0][1].role == "executor"
    assert recorded.status == "failed"


def test_contract_has_no_plan_execute_or_composite():
    public = {n for n in dir(Agent) if not n.startswith("_")}
    assert "run" in public
    assert "role" in public
    assert "plan" not in public
    assert "execute" not in public
    assert "children" not in public
    assert "agents" not in public


def test_run_and_slack_do_not_import_concrete_agents():
    for path in _iter_py(_PRODUCT_NO_CONCRETE):
        if path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names.extend(alias.name.split(".")[-1] for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                names.extend(alias.name for alias in node.names)
            for name in names:
                assert name not in _CONCRETE_AGENTS, f"{path} imports {name}"
        text = path.read_text(encoding="utf-8")
        for name in _CONCRETE_AGENTS:
            assert name not in text, f"{path.relative_to(_REPO)} mentions {name}"


def test_no_agent_runtime_env_for_roles():
    assert "agent_runtime" not in Settings.model_fields
