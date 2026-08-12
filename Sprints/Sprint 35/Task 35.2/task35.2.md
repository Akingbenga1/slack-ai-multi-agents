# Task 35.2 — `EmbeddingProvider` + TEI adapter

## Steps

- [x] Define `EmbeddingProvider` Strategy: `embed(texts) -> vectors` of configured dim
- [x] Implement TEI adapter (wraps / owns `TeiClient`); dim + model id stay on the adapter
- [x] Factory `get_embedding_provider` via `EMBEDDING_PROVIDER` (`tei` default; `ollama` / `openai` stub or raise)
- [x] Add `embedding_provider` setting; keep `TEI_URL` / `EMBEDDING_MODEL_ID` / `EMBEDDING_DIM` as adapter secrets
- [x] Light smoke: factory + dim check via TEI adapter (mocked HTTP optional)

## Acceptance criteria

- [x] Ingest/retrieve can talk to an `EmbeddingProvider`; TEI is one adapter
- [x] `embed(texts) -> vectors` is on the interface; dim / model id are adapter-owned
- [x] `EMBEDDING_PROVIDER=tei|ollama|openai` selects the adapter (non-TEI may be stub/extension)
