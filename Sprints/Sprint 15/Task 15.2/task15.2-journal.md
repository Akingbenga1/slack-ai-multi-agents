# Task 15.2 journal

## Status

`completed`

## Summary

Registered MCP tool `search_knowledge` that wraps `api.app.retrieval.search_knowledge` with mandatory `client_id` (fail-closed via `require_client_id`). Optional filters and citation dict serialization included.

## Acceptance criteria checklist

- [x] Tool listed on stdio server
- [x] Missing `client_id` fails closed
- [x] Tenant-scoped hits returned as JSON-friendly payload

## Decision log

- Tool implementation in `mcp_server/tools/search.py`; FastMCP registers thin wrappers in `create_mcp`.
- Reuse existing retrieval library (no duplicate Qdrant logic).

## Needs human

None.

## Files changed

- `mcp_server/tools/search.py`, `serialize.py`, `server.py`
- `tests/mcp/test_server.py`
- `docs/mcp.md`, `docs/retrieval.md`
- `Sprints/Sprint 15/Task 15.2/*`

## Resume notes

Next in batch: **Task 15.3 — draft_meeting_brief**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/mcp -q  →  6 passed
```
