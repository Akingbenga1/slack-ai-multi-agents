"""Unit tests for search_knowledge (Task 10.1)."""

from __future__ import annotations

import pytest

from api.app.qdrant import TenantFilterRequired, upsert_vectors
from api.app.retrieval import KnowledgeSearchFilters, search_knowledge
from tests.retrieval.helpers import (
    TENANT_A,
    StubTei,
    memory_client,
    memory_settings,
    unit_vector,
)


def test_search_knowledge_returns_citations_with_metadata():
    settings = memory_settings()
    client = memory_client()
    vec = unit_vector(0)
    upsert_vectors(
        client_id=TENANT_A,
        vectors=[vec],
        payloads=[
            {
                "kind": "slack_message",
                "channel": "C_KNOWLEDGE",
                "ts": "1710000000.000100",
                "user": "U1",
                "text": "Sprint ten sample dump about onboarding checklist",
                "message_text": "Sprint ten sample dump about onboarding checklist",
                "source_format": "json",
                "chunk_index": 0,
            }
        ],
        ids=["11111111-1111-1111-1111-111111111111"],
        client=client,
        settings=settings,
    )

    tei = StubTei({"onboarding": vec})
    result = search_knowledge(
        client_id=TENANT_A,
        query="onboarding checklist",
        limit=5,
        settings=settings,
        tei=tei,  # type: ignore[arg-type]
        client=client,
    )

    assert result.client_id == TENANT_A
    assert result.query == "onboarding checklist"
    assert len(result.hits) == 1
    hit = result.hits[0]
    assert hit.kind == "slack_message"
    assert hit.channel == "C_KNOWLEDGE"
    assert hit.ts == "1710000000.000100"
    assert "onboarding" in hit.text.lower()
    assert hit.client_id == TENANT_A
    assert "slack" in hit.short_label()


def test_search_knowledge_optional_kind_filter():
    settings = memory_settings()
    client = memory_client()
    vec_slack = unit_vector(0)
    vec_doc = unit_vector(1)
    upsert_vectors(
        client_id=TENANT_A,
        vectors=[vec_slack, vec_doc],
        payloads=[
            {
                "kind": "slack_message",
                "channel": "C1",
                "ts": "1.0",
                "text": "slack only",
            },
            {
                "kind": "document",
                "filename": "policy.csv",
                "locator": "sheet=Sheet1 row=2",
                "text": "refund policy within 30 days",
            },
        ],
        ids=[
            "22222222-2222-2222-2222-222222222221",
            "22222222-2222-2222-2222-222222222222",
        ],
        client=client,
        settings=settings,
    )

    # Query vector closer to document; without filter both are eligible by score.
    tei = StubTei({"refund": vec_doc}, default=vec_doc)
    filtered = search_knowledge(
        client_id=TENANT_A,
        query="refund policy",
        filters=KnowledgeSearchFilters(kind="document"),
        limit=5,
        settings=settings,
        tei=tei,  # type: ignore[arg-type]
        client=client,
    )
    assert len(filtered.hits) == 1
    assert filtered.hits[0].kind == "document"
    assert filtered.hits[0].filename == "policy.csv"

    slack_only = search_knowledge(
        client_id=TENANT_A,
        query="refund policy",
        filters={"kind": "slack_message"},
        limit=5,
        settings=settings,
        tei=tei,  # type: ignore[arg-type]
        client=client,
    )
    assert len(slack_only.hits) == 1
    assert slack_only.hits[0].kind == "slack_message"
    assert slack_only.hits[0].channel == "C1"


def test_search_knowledge_empty_query_rejected():
    with pytest.raises(ValueError, match="query"):
        search_knowledge(
            client_id=TENANT_A,
            query="  ",
            settings=memory_settings(),
            tei=StubTei({}),  # type: ignore[arg-type]
            client=memory_client(),
        )


def test_search_knowledge_missing_client_id_fail_closed():
    with pytest.raises(TenantFilterRequired):
        search_knowledge(
            client_id=None,
            query="hello",
            settings=memory_settings(),
            tei=StubTei({"hello": unit_vector(0)}),  # type: ignore[arg-type]
            client=memory_client(),
        )
