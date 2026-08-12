# Task 35.3 journal

## Status

`completed`

## Summary

Wired `ingest_chunks` and `search_knowledge` to `EmbeddingProvider` + `VectorStore`. Citations map from vendor-neutral `VectorHit`. `/health` deep checks use `vector_store` / `embedding` keys and only probe Qdrant `/readyz` or TEI `/health` when that adapter is selected. Pipelines pass through the interfaces; demo default remains Qdrant + TEI.

## Acceptance criteria checklist

- [x] `ingest_chunks` / `search_knowledge` call interfaces, not vendor clients by name
- [x] `/health` probes the selected adapters
- [x] Demo default remains Qdrant + TEI; adapter secrets keep existing names

## Decision log

- **Health keys:** `vector_store` + `embedding` (each includes `adapter`); Qdrant/TEI probe URLs only when selected — matches jira “not by name unless selected.”
- **Pipelines** (`pipeline.py` / `document_pipeline.py`) take optional `embeddings` / `store`; no `TeiClient` / `QdrantClient` in product ingest signatures.
- **`citation_from_hit`** primary; `citation_from_point` kept as thin alias for any leftover ScoredPoint callers.
- **Worker source assert** updated: core must call `store.upsert`, not `upsert_vectors`.

## Needs human

None new.

## Files changed

- `api/app/ingest/chunks_ingest.py`, `pipeline.py`, `document_pipeline.py`
- `api/app/retrieval/search.py`, `citations.py`, `__init__.py`
- `api/app/health.py`
- `api/app/demo/isolation.py`
- `tests/ingest/test_chunks_ingest.py`
- `tests/retrieval/*`
- `tests/worker/test_tenant_job.py`
- `tests/admin/test_admin_api.py`

## Resume notes

Done. Continue Task 35.4 — isolation + regression (fail-closed tenant tests + ingest/search/MCP green; demo default Qdrant + TEI).

## Open questions

None.

## Smoke test results

`uv run pytest tests/ingest/test_chunks_ingest.py tests/retrieval/ tests/vector_store/ tests/embedding/ tests/worker/test_tenant_job.py tests/admin/test_admin_api.py::test_admin_health_owner_only -q` → 27 passed.
