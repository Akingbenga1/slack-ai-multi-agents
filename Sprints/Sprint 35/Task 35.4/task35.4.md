# Task 35.4 — Isolation + regression

## Steps

- [x] Fail-closed tenant filter tests still pass (`tests/retrieval/test_tenant_isolation.py` + adapter factory smoke)
- [x] Product ingest/retrieve surface must not import Qdrant/TEI clients by name (source isolation scan)
- [x] Move `CLIENT_ID_PAYLOAD_KEY` to vendor-neutral vector-store types; citations stop importing `api.app.qdrant`
- [x] Existing ingest / search / MCP `search_knowledge` tests green
- [x] Docs: retrieval + adapter notes reflect Strategy/Factory; demo default remains Qdrant + TEI
- [x] Mark vector-store + embedding-provider gaps Implemented in `Project-Documents/review.md`

## Acceptance criteria

- [x] Fail-closed tenant filter tests still pass
- [x] Existing ingest/search/MCP `search_knowledge` tests green; demo default remains Qdrant + TEI
- [x] Sprint 35 exit: switching vector store or embedder is env + adapter; ingest/retrieve are not rewritten
