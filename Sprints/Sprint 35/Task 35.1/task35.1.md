# Task 35.1 — `VectorStore` + Qdrant adapter

## Steps

- [x] Define `VectorStore` Strategy: upsert, search, ensure-collection; mandatory `client_id` on every call
- [x] Vendor-neutral hit / filter types (no `qdrant_client` models on the interface)
- [x] Implement `QdrantVectorStore` Adapter (wraps existing `api.app.qdrant` helpers)
- [x] Factory `get_vector_store` via `VECTOR_STORE` (`qdrant` default; `pgvector` stub/extension)
- [x] Add `vector_store` setting; keep `QDRANT_*` as adapter secrets
- [x] Light smoke: factory + fail-closed tenant filter via adapter

## Acceptance criteria

- [x] Knowledge storage talks to a `VectorStore`; Qdrant is one adapter
- [x] Upsert / search / ensure-collection are on the interface with mandatory `client_id`
- [x] `VECTOR_STORE=qdrant|pgvector` selects the adapter (pgvector may raise not-implemented)
