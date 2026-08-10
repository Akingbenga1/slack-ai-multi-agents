# Task 10.1 journal

## Status

`completed`

## Summary

Added `api/app/retrieval.search_knowledge`: TEI-embed query → tenant-scoped Qdrant top-k → `KnowledgeCitation` metadata (Slack channel/ts or document filename/locator). Optional filters (`kind`, `channel`, `filename`) AND'd via `search_vectors(extra_conditions=)`.

## Acceptance criteria checklist

- [x] Top-k tenant-scoped search — done
- [x] Citation metadata — done (`KnowledgeCitation` + `short_label`)
- [x] Fail-closed missing `client_id` — done
- [x] Ready for 10.2 / 10.3 — done

## Decision log

- Library under `api/app/retrieval/` (not HTTP yet); MCP (Sprint 15) will wrap the same function.
- Default top-k = 8; callers pass `limit`.
- Defense-in-depth: drop any hit whose payload `client_id` ≠ query tenant after search.
- Filters as dataclass or plain mapping for MCP/JSON friendliness.

## Needs human

None.

## Files changed

- `api/app/retrieval/` (`__init__`, `search`, `types`, `citations`)
- `api/app/qdrant/vectors.py` (`extra_conditions`)
- `tests/retrieval/test_search_knowledge.py`, `helpers.py`
- `docs/retrieval.md`, `docs/qdrant-tei.md`, `README.md`
- `Sprints/Sprint 10/Task 10.1/*`

## Resume notes

Next in batch: **Task 10.2 — Fail-closed tenant filter tests**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/retrieval -q  →  8 passed (full suite after 10.2)
```
