"""Knowledge ingest/retrieve vendor isolation (Sprint 35.4)."""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_APP = _REPO / "api" / "app"

# Product surface must not name vector/embed vendors (Strategy + Adapter boundary).
_FORBIDDEN = re.compile(
    r"\b(qdrant|tei|teiclient|qdrantclient|scoredpoint|upsert_vectors|search_vectors)\b",
    re.IGNORECASE,
)

_ISOLATED_MODULES = (
    _APP / "ingest" / "chunks_ingest.py",
    _APP / "ingest" / "pipeline.py",
    _APP / "ingest" / "document_pipeline.py",
    _APP / "retrieval" / "search.py",
    _APP / "retrieval" / "citations.py",
)


def test_ingest_retrieve_have_no_vendor_names():
    for path in _ISOLATED_MODULES:
        text = path.read_text(encoding="utf-8")
        hit = _FORBIDDEN.search(text)
        assert hit is None, f"{path.name} mentions vendor {hit.group(0)!r}"


def test_ingest_retrieve_use_strategy_interfaces():
    chunks = (_APP / "ingest" / "chunks_ingest.py").read_text(encoding="utf-8")
    search = (_APP / "retrieval" / "search.py").read_text(encoding="utf-8")
    assert "EmbeddingProvider" in chunks and "VectorStore" in chunks
    assert "get_embedding_provider" in chunks and "get_vector_store" in chunks
    assert "embeddings.embed(" in chunks
    assert "store.upsert(" in chunks
    assert "EmbeddingProvider" in search and "VectorStore" in search
    assert "store.search(" in search
    assert "TeiClient" not in chunks and "TeiClient" not in search
    assert "QdrantClient" not in chunks and "QdrantClient" not in search


def test_demo_defaults_remain_qdrant_and_tei():
    from api.app.settings import Settings

    s = Settings()
    assert s.vector_store == "qdrant"
    assert s.embedding_provider == "tei"
