"""Guardrails: hard hedge + tenant filter never dropped (Task 13.4)."""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver

from api.app.agent.guardrails import (
    HEDGE_MESSAGE,
    TenantContextRequired,
    filter_chunks_for_tenant,
    require_tenant_client_id,
    should_hedge,
)
from api.app.agent.llm import StubChatModel
from api.app.agent.run import run_agent
from api.app.retrieval.types import KnowledgeCitation, KnowledgeSearchResult
from api.app.settings import Settings

TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OTHER = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def test_require_tenant_client_id_fail_closed():
    with pytest.raises(TenantContextRequired):
        require_tenant_client_id(None, where="test")
    with pytest.raises(TenantContextRequired):
        require_tenant_client_id("  ", where="test")
    assert require_tenant_client_id(TENANT) == TENANT


def test_filter_chunks_drops_foreign_tenant():
    chunks = [
        {"client_id": TENANT, "text": "ours", "point_id": "1", "score": 0.9},
        {"client_id": OTHER, "text": "theirs", "point_id": "2", "score": 0.99},
        {"client_id": TENANT, "text": "also ours", "point_id": "3", "score": 0.85},
    ]
    filtered = filter_chunks_for_tenant(chunks, TENANT)
    assert [c["point_id"] for c in filtered] == ["1", "3"]
    assert should_hedge([]) is True
    assert should_hedge(filtered) is False


def test_filter_chunks_drops_weak_scores():
    chunks = [
        {"client_id": TENANT, "text": "weak", "point_id": "1", "score": 0.55},
        {"client_id": TENANT, "text": "strong", "point_id": "2", "score": 0.82},
    ]
    filtered = filter_chunks_for_tenant(chunks, TENANT, min_score=0.70)
    assert [c["point_id"] for c in filtered] == ["2"]


def test_retrieve_drops_foreign_hits_from_search():
    """Even if search_fn returns another tenant's hit, it must not reach compose."""

    def leaky_search(*, client_id, query, limit=8, settings=None, **_kw):
        return KnowledgeSearchResult(
            client_id=str(client_id),
            query=query,
            hits=[
                KnowledgeCitation(
                    point_id="foreign",
                    score=0.99,
                    text="SECRET from other tenant",
                    kind="document",
                    client_id=OTHER,
                    filename="leak.csv",
                ),
                KnowledgeCitation(
                    point_id="ours",
                    score=0.8,
                    text="Refunds within 30 days.",
                    kind="document",
                    client_id=TENANT,
                    filename="policy.csv",
                ),
            ],
            limit=limit,
        )

    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    out = run_agent(
        client_id=TENANT,
        question="What is the refund policy?",
        conversation_id="guard-1",
        settings=settings,
        checkpointer=MemorySaver(),
        search_fn=leaky_search,
        chat_model=StubChatModel(),
        record_usage=False,
    )
    assert out["client_id"] == TENANT
    assert out["hedge"] is False
    assert len(out["retrieved_chunks"]) == 1
    assert out["retrieved_chunks"][0]["client_id"] == TENANT
    assert "SECRET" not in out["answer"]
    assert "Refunds" in out["answer"] or "stub:haiku" in out["answer"]


def test_hard_hedge_when_only_weak_scores():
    def weak_search(*, client_id, query, limit=8, score_threshold=None, settings=None, **_kw):
        return KnowledgeSearchResult(
            client_id=str(client_id),
            query=query,
            hits=[
                KnowledgeCitation(
                    point_id="weak",
                    score=0.55,
                    text="Barely related neighbor",
                    kind="document",
                    client_id=TENANT,
                    filename="noise.csv",
                )
            ],
            limit=limit,
        )

    settings = Settings(
        agent_checkpointer="memory",
        anthropic_api_key="",
        agent_min_score=0.70,
    )
    out = run_agent(
        client_id=TENANT,
        question="asdkfjhasdkfjh random gibberish",
        conversation_id="guard-weak",
        settings=settings,
        checkpointer=MemorySaver(),
        search_fn=weak_search,
        chat_model=StubChatModel(),
        record_usage=False,
    )
    assert out["hedge"] is True
    assert out["answer"] == HEDGE_MESSAGE
    assert out["retrieved_chunks"] == []


def test_missing_client_id_raises_before_search():
    from api.app.agent.graph import build_agent_graph
    from langchain_core.messages import HumanMessage

    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    called = {"search": False}

    def search(*, client_id, query, limit=8, settings=None, **_kw):
        called["search"] = True
        return KnowledgeSearchResult(
            client_id=str(client_id), query=query, hits=[], limit=limit
        )

    graph = build_agent_graph(
        settings=settings,
        checkpointer=MemorySaver(),
        search_fn=search,
        chat_model=StubChatModel(),
    )
    with pytest.raises(TenantContextRequired):
        graph.invoke(
            {
                "client_id": "",
                "messages": [HumanMessage(content="hi")],
                "question": "hi",
                "retrieved_chunks": [],
                "workflow": "qa",
                "model_tier": "haiku",
            },
            {"configurable": {"thread_id": "x"}},
        )
    assert called["search"] is False


def test_grounded_dry_run_answers_for_one_tenant():
    """Sprint 13 exit: dry-run returns a grounded answer for one tenant."""

    def fake_search(*, client_id, query, limit=8, settings=None, **_kw):
        assert client_id == TENANT
        return KnowledgeSearchResult(
            client_id=str(client_id),
            query=query,
            hits=[
                KnowledgeCitation(
                    point_id="11111111-1111-1111-1111-111111111111",
                    score=0.93,
                    text="Customers may request a full refund within 30 days of purchase.",
                    kind="document",
                    client_id=TENANT,
                    filename="sample_doc.csv",
                )
            ],
            limit=limit,
        )

    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    out = run_agent(
        client_id=TENANT,
        question="What is the refund policy?",
        conversation_id="exit-1",
        settings=settings,
        checkpointer=MemorySaver(),
        search_fn=fake_search,
        chat_model=StubChatModel(),
        record_usage=False,
    )
    assert out["hedge"] is False
    assert out["client_id"] == TENANT
    assert len(out["retrieved_chunks"]) == 1
    assert "30 days" in out["retrieved_chunks"][0]["text"]
    assert out["answer"]
    assert out["answer"] != HEDGE_MESSAGE
    assert "stub:haiku" in out["answer"]
