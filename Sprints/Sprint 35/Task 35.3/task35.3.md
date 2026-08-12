# Task 35.3 — Wire ingest, retrieve, health

## Steps

- [x] `ingest_chunks` takes `EmbeddingProvider` + `VectorStore` (not `TeiClient` / `qdrant_client` by name)
- [x] `search_knowledge` takes the interfaces; citations map from `VectorHit`
- [x] `/health` probes selected adapters (not Qdrant `/readyz` + TEI `/health` by name unless selected)
- [x] Keep `QDRANT_*` / `TEI_*` / `EMBEDDING_MODEL_ID` / `EMBEDDING_DIM` as adapter secrets — do not rename
- [x] No new pgvector / OpenAI-embed / Ollama-embed env keys unless that adapter ships
- [x] Confirm `.env.example` has `VECTOR_STORE` + `EMBEDDING_PROVIDER` selectors
- [x] Light smoke: existing ingest/search unit tests still green (mocked)

## Acceptance criteria

- [x] `ingest_chunks` / `search_knowledge` call interfaces, not vendor clients by name
- [x] `/health` probes the selected adapters
- [x] Demo default remains Qdrant + TEI; adapter secrets keep existing names
