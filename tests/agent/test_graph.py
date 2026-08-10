"""Graph state & nodes (Task 13.1) + checkpointer thread key (13.2)."""

from __future__ import annotations

from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver

from api.app.agent.checkpointer import thread_id_for_tenant
from api.app.agent.llm import StubChatModel
from api.app.agent.run import run_agent
from api.app.retrieval.types import KnowledgeCitation, KnowledgeSearchResult
from api.app.settings import Settings

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def _fake_search(*, client_id, query, limit=8, settings=None, **_kw):
    assert client_id == TENANT
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


def test_run_agent_route_retrieve_compose():
    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    out = run_agent(
        client_id=TENANT,
        question="What is the refund policy?",
        conversation_id="t1",
        settings=settings,
        checkpointer=MemorySaver(),
        search_fn=_fake_search,
        chat_model=StubChatModel(),
        record_usage=False,
    )
    assert out["client_id"] == TENANT
    assert out["workflow"] == "qa"
    assert out["model_tier"] == "haiku"
    assert out["hedge"] is False
    assert len(out["retrieved_chunks"]) == 1
    assert out["retrieved_chunks"][0]["client_id"] == TENANT
    assert "stub:haiku" in out["answer"]
    assert out["thread_id"] == thread_id_for_tenant(TENANT, "t1")


def test_run_agent_hedges_when_no_hits():
    from api.app.agent.guardrails import HEDGE_MESSAGE

    def empty_search(*, client_id, query, limit=8, settings=None, **_kw):
        return KnowledgeSearchResult(
            client_id=str(client_id), query=query, hits=[], limit=limit
        )

    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    out = run_agent(
        client_id=TENANT,
        question="obscure topic with no corpus",
        conversation_id="t2",
        settings=settings,
        checkpointer=MemorySaver(),
        search_fn=empty_search,
        chat_model=StubChatModel(),
        record_usage=False,
    )
    assert out["hedge"] is True
    assert out["retrieved_chunks"] == []
    assert out["answer"] == HEDGE_MESSAGE
    assert out["usage_tokens"] == 0


def test_thread_id_scoped_per_tenant():
    a = thread_id_for_tenant(TENANT, "slack:123")
    other = str(uuid4())
    b = thread_id_for_tenant(other, "slack:123")
    assert a.startswith(TENANT + ":")
    assert a != b
    assert ":" not in a.split(":", 1)[1]  # conversation id sanitized


def test_sonnet_escalation_in_graph():
    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    out = run_agent(
        client_id=TENANT,
        question="Compare refund vs exchange policies in detail",
        conversation_id="t3",
        settings=settings,
        checkpointer=MemorySaver(),
        search_fn=_fake_search,
        chat_model=StubChatModel(),
        record_usage=False,
    )
    assert out["model_tier"] == "sonnet"
    assert "compare" in out["complexity_flags"]
    assert "stub:sonnet" in out["answer"]


def test_memory_checkpointer_thread_continuity():
    """Same conversation_id accumulates messages across invokes."""
    from api.app.agent.graph import build_agent_graph
    from langchain_core.messages import HumanMessage

    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    saver = MemorySaver()
    graph = build_agent_graph(
        settings=settings,
        checkpointer=saver,
        search_fn=_fake_search,
        chat_model=StubChatModel(),
    )
    thread_id = thread_id_for_tenant(TENANT, "cont-1")
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke(
        {
            "client_id": TENANT,
            "messages": [HumanMessage(content="What is the refund policy?")],
            "question": "What is the refund policy?",
            "retrieved_chunks": [],
            "workflow": "qa",
            "model_tier": "haiku",
        },
        config,
    )
    graph.invoke(
        {
            "client_id": TENANT,
            "messages": [HumanMessage(content="And the window?")],
            "question": "And the window?",
            "retrieved_chunks": [],
            "workflow": "qa",
            "model_tier": "haiku",
        },
        config,
    )
    snap = graph.get_state(config)
    msgs = snap.values.get("messages") or []
    assert len(msgs) >= 4  # 2 human + 2 ai
