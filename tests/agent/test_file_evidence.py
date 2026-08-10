"""Attached evidence flows into agent compose (Sprint 23.1 smoke)."""

from __future__ import annotations

from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver

from api.app.agent.llm import StubChatModel
from api.app.agent.run import run_agent
from api.app.retrieval.types import KnowledgeCitation, KnowledgeSearchResult
from api.app.settings import Settings


def test_run_agent_file_analyse_uses_attachment_not_hedge():
    cid = str(uuid4())

    def search_fn(**_kwargs):
        return KnowledgeSearchResult(hits=[], query="q", client_id=cid)

    result = run_agent(
        client_id=cid,
        question="Analyse this attached financial report for competitors",
        conversation_id="test-file-1",
        settings=Settings(
            agent_checkpointer="memory",
            anthropic_api_key="",
            agent_retrieve_backend="direct",
        ),
        checkpointer=MemorySaver(),
        chat_model=StubChatModel(),
        search_fn=search_fn,
        record_usage=False,
        attached_evidence=[
            {
                "client_id": cid,
                "file_id": "F1",
                "filename": "report.csv",
                "text": "competitor,share\nAcme,40\nBeta,25\n",
                "mimetype": "text/csv",
            }
        ],
    )
    assert result["workflow"] == "file_analyse"
    assert result["hedge"] is False
    assert result["answer"]
    assert any(
        (c.get("kind") == "attachment") for c in result["retrieved_chunks"]
    )
    assert any("Acme" in (c.get("text") or "") for c in result["retrieved_chunks"])


def test_run_agent_drops_foreign_attachment():
    cid = str(uuid4())
    other = str(uuid4())

    def search_fn(**_kwargs):
        return KnowledgeSearchResult(
            hits=[
                KnowledgeCitation(
                    point_id="p1",
                    score=0.9,
                    text="refund policy is 30 days",
                    kind="document",
                    client_id=cid,
                    filename="policy.pdf",
                )
            ],
            query="q",
            client_id=cid,
        )

    result = run_agent(
        client_id=cid,
        question="What is the refund policy?",
        conversation_id="test-file-2",
        settings=Settings(
            agent_checkpointer="memory",
            anthropic_api_key="",
            agent_retrieve_backend="direct",
        ),
        checkpointer=MemorySaver(),
        chat_model=StubChatModel(),
        search_fn=search_fn,
        record_usage=False,
        attached_evidence=[
            {
                "client_id": other,
                "file_id": "Fleak",
                "filename": "secret.csv",
                "text": "SHOULD_NOT_APPEAR",
            }
        ],
    )
    texts = " ".join(c.get("text") or "" for c in result["retrieved_chunks"])
    assert "SHOULD_NOT_APPEAR" not in texts
