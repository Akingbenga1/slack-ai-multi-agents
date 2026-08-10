# Task 10.1 — `search_knowledge(client_id, query, filters?)`

## Steps

- [x] Add retrieval library module (`api/app/retrieval/`) with `search_knowledge`
- [x] Require `client_id` (fail-closed); embed query via TEI; search Qdrant top-k
- [x] Optional filters (`kind`, `channel`, `filename`) AND'd with tenant filter
- [x] Return hits with metadata citations (Slack + document payload fields)
- [x] Light unit tests (mock TEI / in-memory Qdrant)
- [x] Document usage for agent / MCP wiring

## Acceptance criteria

- [x] `search_knowledge(client_id, query, filters?)` returns top-k hits scoped to tenant
- [x] Each hit includes citation metadata (kind, source locator, text snippet, score)
- [x] Missing / empty `client_id` raises fail-closed (no unscoped search)
- [x] Ready for Task 10.2 isolation tests and Task 10.3 corpus smoke
