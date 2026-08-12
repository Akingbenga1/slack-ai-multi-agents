# Task 35.2 journal

## Status

`completed`

## Summary

Introduced `EmbeddingProvider` Strategy + `get_embedding_provider` Factory and `TeiEmbeddingProvider` Adapter wrapping `TeiClient`. Dim / model id stay on the adapter; `TEI_*` / `EMBEDDING_*` secrets unchanged. Ingest/retrieve still construct `TeiClient` until Task 35.3.

## Acceptance criteria checklist

- [x] Ingest/retrieve can talk to an `EmbeddingProvider`; TEI is one adapter
- [x] `embed(texts) -> vectors` is on the interface; dim / model id are adapter-owned
- [x] `EMBEDDING_PROVIDER=tei|ollama|openai` selects the adapter (non-TEI may be stub/extension)

## Decision log

- **Patterns:** Strategy (`EmbeddingProvider`) + Factory (`get_embedding_provider`) + Adapter (`TeiEmbeddingProvider` / `TeiClient`).
- **`TeiClient` kept** as adapter-internal HTTP client (same as `stripe_client` under Stripe).
- **ollama / openai** raise not-implemented (documented stubs; no new env keys).
- **`.env.example`** adds `EMBEDDING_PROVIDER`; existing TEI keys stay.

## Needs human

None new.

## Files changed

- `api/app/embedding/` (`provider.py`, `tei_adapter.py`, `__init__.py`)
- `api/app/settings.py` (`embedding_provider`)
- `.env.example` (`EMBEDDING_PROVIDER`)
- `tests/embedding/test_embedding_provider_factory.py`

## Resume notes

Done. Continue Task 35.3 — wire ingest, retrieve, health to the interfaces.

## Open questions

None.

## Smoke test results

`uv run pytest tests/embedding/test_embedding_provider_factory.py tests/vector_store/test_vector_store_factory.py -q` → 10 passed.
