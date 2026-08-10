# Task 6.1 journal

## Status

`completed`

## Summary

Added `api/app/qdrant/` with `ensure_knowledge_collection()` (384-dim Cosine collection + `client_id` keyword index) and fail-closed `upsert_vectors` / `search_vectors` that require `client_id`.

## Acceptance criteria checklist

- [x] Collection + `client_id` index — done (`knowledge`)
- [x] Missing `client_id` raises — done (`TenantFilterRequired`)
- [x] Filter / payload always stamped — done

## Decision log

- Shared collection `knowledge` with payload filter (not per-tenant collections).
- `EMBEDDING_DIM=384` aligned with Compose TEI `BAAI/bge-small-en-v1.5`.
- Search uses `query_points` + mandatory `query_filter` (qdrant-client 1.19).
- Client `check_compatibility=False` vs Compose Qdrant 1.13.2.

## Needs human

None for this task.

## Files changed

- `api/app/settings.py`
- `api/app/qdrant/` (`client`, `collection`, `tenant`, `vectors`)
- `.env.example`

## Resume notes

Continue Task 6.2 (same batch).

## Open questions

None.
