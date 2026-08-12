# Task 35.1 journal

## Status

`completed`

## Summary

Introduced `VectorStore` Strategy + `get_vector_store` Factory and `QdrantVectorStore` Adapter. Adapter wraps existing `api.app.qdrant` upsert/search/ensure-collection; tenant `client_id` stays fail-closed. Product ingest/retrieve still call Qdrant helpers directly until Task 35.3.

## Acceptance criteria checklist

- [x] Knowledge storage talks to a `VectorStore`; Qdrant is one adapter
- [x] Upsert / search / ensure-collection are on the interface with mandatory `client_id`
- [x] `VECTOR_STORE=qdrant|pgvector` selects the adapter (pgvector may raise not-implemented)

## Decision log

- **Patterns:** Strategy (`VectorStore`) + Factory (`get_vector_store`) + Adapter (`QdrantVectorStore` / existing `qdrant` module helpers).
- **Vendor-neutral `VectorHit` + equality `VectorFilters`** so search_knowledge will not need `qdrant_client.http.models` after wiring (35.3).
- **`api.app.qdrant` kept** as adapter-internal helpers (same shape as `stripe_client` under Stripe adapter).
- **`VECTOR_STORE` + `.env.example`** added early (matches Sprint 33/34 selector pattern); `QDRANT_*` names unchanged.
- **pgvector** raises not-implemented (documented stub only).

## Needs human

None new.

## Files changed

- `api/app/vector_store/` (`provider.py`, `qdrant_adapter.py`, `types.py`, `__init__.py`)
- `api/app/settings.py` (`vector_store`)
- `.env.example` (`VECTOR_STORE`)
- `tests/vector_store/test_vector_store_factory.py`

## Resume notes

Done. Continue Task 35.2 — `EmbeddingProvider` + TEI adapter.

## Open questions

None.

## Smoke test results

`uv run pytest tests/vector_store/test_provider_factory.py -q` → 5 passed.
