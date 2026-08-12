"""AgentRuntime adapter smoke + product isolation (Sprint 39)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

from api.app.agent.deps import AgentRuntimeDeps
from api.app.agent.langgraph_adapter import LangGraphAgentRuntime
from api.app.agent.llm import StubChatModel
from api.app.agent.run import run_agent
from api.app.agent.runtime import default_agent_runtime
from api.app.retrieval.types import KnowledgeSearchResult
from api.app.settings import Settings

_REPO = Path(__file__).resolve().parents[2]
_APP = _REPO / "api" / "app"

_FORBIDDEN_GRAPH = re.compile(
    r"\b(StateGraph|AIMessage|from langgraph|import langgraph)\b",
)

# Slack delivery / billing / reports must not take LangGraph graph types.
_PRODUCT_NO_LANGGRAPH = (
    _APP / "slack" / "agent_reply.py",
    _APP / "slack" / "reply_pipeline.py",
    _APP / "slack" / "delivery",
    _APP / "billing",
    _APP / "reports" / "post.py",
)


def _iter_py(paths: tuple[Path, ...]):
    for p in paths:
        if p.is_file():
            yield p
        elif p.is_dir():
            yield from p.rglob("*.py")


def test_default_runtime_is_langgraph():
    rt = default_agent_runtime()
    assert rt.name == "langgraph"
    assert isinstance(rt, LangGraphAgentRuntime)


def test_run_agent_facade_uses_runtime(monkeypatch):
    calls: list[dict] = []

    class _Fake:
        name = "fake"

        def run(self, **kwargs):
            calls.append(kwargs)
            return {
                "client_id": kwargs["client_id"],
                "thread_id": "t",
                "question": kwargs["question"],
                "answer": "ok",
                "workflow": "qa",
                "model_tier": "fast",
                "complexity_flags": [],
                "retrieved_chunks": [],
                "usage_tokens": 0,
                "hedge": True,
                "meeting_draft": "",
                "report_window": "",
                "attached_evidence": [],
            }

        def run_report(self, **kwargs):
            raise AssertionError("unexpected run_report")

    tid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    out = run_agent(
        client_id=tid,
        question="hello",
        record_usage=False,
        runtime=_Fake(),
    )
    assert out["answer"] == "ok"
    assert len(calls) == 1
    assert calls[0]["question"] == "hello"


def test_langgraph_runtime_run_smoke():
    tid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    settings = Settings(llm_provider="stub", agent_checkpointer="memory")

    def _search(*, client_id, query, limit=8, settings=None, **_kw):
        return KnowledgeSearchResult(
            client_id=str(client_id), query=query, hits=[], limit=limit
        )

    result = LangGraphAgentRuntime().run(
        client_id=tid,
        question="anything",
        conversation_id="sprint39",
        deps=AgentRuntimeDeps(
            settings=settings,
            checkpointer=MemorySaver(),
            search_fn=_search,
            chat_model=StubChatModel(),
        ),
        record_usage=False,
    )
    assert result["client_id"] == tid
    assert result["thread_id"].startswith(tid)
    assert "answer" in result
    assert result["hedge"] is True


def test_slack_billing_reports_do_not_import_langgraph_types():
    for path in _iter_py(_PRODUCT_NO_LANGGRAPH):
        if path.name == "__pycache__" or path.suffix != ".py":
            continue
        text = path.read_text(encoding="utf-8")
        hit = _FORBIDDEN_GRAPH.search(text)
        assert hit is None, f"{path.relative_to(_REPO)} mentions {hit.group(0)!r}"


def test_product_facade_run_does_not_import_stategraph():
    """run.py is the product facade — no StateGraph / HumanMessage."""
    path = _APP / "agent" / "run.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("langgraph.graph"), alias.name
                assert alias.name != "langchain_core.messages", alias.name
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("langgraph.graph"), node.module
            assert node.module != "langchain_core.messages", node.module
    text = path.read_text(encoding="utf-8")
    assert "StateGraph" not in text
    assert "HumanMessage" not in text
    assert "default_agent_runtime" in text


def test_no_agent_runtime_env_key():
    """Sprint 39: no AGENT_RUNTIME factory until a second runtime exists."""
    assert "agent_runtime" not in Settings.model_fields
    s = Settings()
    assert hasattr(s, "agent_checkpointer")


def test_stategraph_owned_by_langgraph_adapter():
    adapter = (_APP / "agent" / "langgraph_adapter.py").read_text(encoding="utf-8")
    assert "StateGraph" in adapter
    assert "LangGraphAgentRuntime" in adapter
