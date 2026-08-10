# Task 10.2 journal

## Status

`completed`

## Summary

Automated isolation tests use in-memory Qdrant + stub TEI: tenant A query embedding aligned with tenant B's vector still never returns B's points; missing/empty `client_id` raises `TenantFilterRequired`; mismatched upsert payload `client_id` rejected.

## Acceptance criteria checklist

- [x] Tenant A never returns B — done
- [x] Fail-closed missing `client_id` — done

## Decision log

- In-memory Qdrant (`QdrantClient(":memory:")`) keeps CI free of Compose.
- Stub TEI maps query substrings → fixed unit vectors so isolation is deterministic.

## Needs human

None.

## Files changed

- `tests/retrieval/test_tenant_isolation.py`
- `tests/retrieval/helpers.py`
- `Sprints/Sprint 10/Task 10.2/*`

## Resume notes

Next in batch: **Task 10.3 — Smoke queries on sample corpus**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/retrieval -q  →  8 passed
```
