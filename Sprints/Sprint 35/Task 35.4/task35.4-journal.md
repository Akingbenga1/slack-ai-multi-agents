# Task 35.4 journal

## Status

`completed`

## Summary

Locked knowledge ingest/retrieve behind `EmbeddingProvider` + `VectorStore`: citations no longer import `api.app.qdrant`; added source-scan isolation tests; docs and `review.md` gaps marked Implemented. Fail-closed tenant + ingest/search/MCP suites green. Demo default remains Qdrant + TEI. Sprint 35 exit met.

## Acceptance criteria checklist

- [x] Fail-closed tenant filter tests still pass
- [x] Existing ingest/search/MCP `search_knowledge` tests green; demo default remains Qdrant + TEI
- [x] Sprint 35 exit: switching vector store or embedder is env + adapter; ingest/retrieve are not rewritten

## Decision log

- **`CLIENT_ID_PAYLOAD_KEY`:** product constant lives in `vector_store.types`; Qdrant `collection.py` keeps a local twin (`"client_id"`) so adapters do not import `vector_store` (circular import via package `__init__`).
- **Isolation scan:** `chunks_ingest` / pipelines / `search` / `citations` must not name Qdrant/TEI helpers; adapters + factory remain the only place that do.

## Needs human

None new.

## Files changed

- `api/app/vector_store/types.py`, `__init__.py`
- `api/app/retrieval/citations.py`
- `api/app/ingest/chunks_ingest.py`, `upload_ingest.py`, `schema.py`
- `tests/retrieval/test_knowledge_isolation.py` (new)
- `docs/retrieval.md`, `docs/qdrant-tei.md`, `docs/celery.md`
- `Project-Documents/review.md`

## Smoke test results

- `uv run pytest tests/retrieval/ tests/ingest/test_chunks_ingest.py tests/vector_store/ tests/embedding/ tests/mcp/test_server.py -q` → **46 passed**

## Resume notes

**Sprint 35 complete.** Next Ralph batch: **Continue Sprint 36 from Task 36.1** — `IdentityProvider` behind token issue.

## Open questions

None.
