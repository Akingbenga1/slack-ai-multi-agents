"""AgentRuntimeDeps factory (Sprint 25.1)."""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

from api.app.agent.deps import AgentRuntimeDeps, build_agent_deps
from api.app.agent.graph import build_agent_graph
from api.app.agent.llm import StubChatModel
from api.app.agent.run import run_agent
from api.app.retrieval.types import KnowledgeCitation, KnowledgeSearchResult
from api.app.settings import Settings

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def _fake_search(*, client_id, query, limit=8, settings=None, **_kw):
    hit = KnowledgeCitation(
        point_id="11111111-1111-1111-1111-111111111111",
        score=0.91,
        text="Refunds are available within 30 days of purchase.",
        kind="document",
        client_id=TENANT,
        filename="policy.csv",
        locator="row:1",
    )
    return KnowledgeSearchResult(
        client_id=str(client_id),
        query=query,
        hits=[hit],
        limit=limit,
    )


def test_build_agent_deps_merges_overrides():
    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    base = AgentRuntimeDeps(settings=settings, search_fn=_fake_search)
    model = StubChatModel()
    merged = build_agent_deps(base, chat_model=model)
    assert merged.settings is settings
    assert merged.search_fn is _fake_search
    assert merged.chat_model is model


def test_run_agent_accepts_deps_bag():
    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    deps = AgentRuntimeDeps(
        settings=settings,
        checkpointer=MemorySaver(),
        search_fn=_fake_search,
        chat_model=StubChatModel(),
    )
    out = run_agent(
        client_id=TENANT,
        question="What is the refund policy?",
        conversation_id="deps-1",
        deps=deps,
        record_usage=False,
    )
    assert out["workflow"] == "qa"
    assert out["hedge"] is False
    assert "stub:fast" in out["answer"]


def test_build_agent_graph_from_deps():
    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    deps = AgentRuntimeDeps(
        settings=settings,
        checkpointer=MemorySaver(),
        search_fn=_fake_search,
        chat_model=StubChatModel(),
    )
    graph = build_agent_graph(deps=deps)
    assert graph is not None
