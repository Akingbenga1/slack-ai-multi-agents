# Qdrant + TEI adapters (Sprint 6+ / 35)

First adapters for the knowledge ``VectorStore`` and ``EmbeddingProvider`` Strategies (Sprint 35). Product ingest/retrieve call the interfaces; this doc covers adapter secrets and low-level helpers.

Sprint 6: collection + fail-closed helpers + TEI client. Sprint 7: Slack history ingest pipeline on top. Sprint 35: factories `VECTOR_STORE` / `EMBEDDING_PROVIDER` (demo defaults `qdrant` / `tei`).

## Config

| Setting | Env | Default |
| ------- | --- | ------- |
| Vector store selector | `VECTOR_STORE` | `qdrant` |
| Embedding provider selector | `EMBEDDING_PROVIDER` | `tei` |
| Qdrant URL (adapter secret) | `QDRANT_URL` | `http://localhost:6333` |
| Collection (adapter secret) | `QDRANT_COLLECTION` | `knowledge` |
| TEI URL (adapter secret) | `TEI_URL` | `http://localhost:8080` |
| Model id (adapter secret) | `EMBEDDING_MODEL_ID` | `BAAI/bge-small-en-v1.5` |
| Vector size (adapter secret) | `EMBEDDING_DIM` | `384` |

Compose TEI must use the same `--model-id` (see `docker-compose.yml`). Do not rename adapter secret env keys.

## Modules

- `api/app/vector_store/` — `VectorStore` + `get_vector_store` + `QdrantVectorStore`
- `api/app/embedding/` — `EmbeddingProvider` + `get_embedding_provider` + `TeiEmbeddingProvider`
- `api/app/qdrant/` — adapter helpers: `ensure_knowledge_collection()`, `upsert_vectors()`, `search_vectors()`
- `api/app/tei/` — `TeiClient.embed()` → `POST {TEI_URL}/embed`
- `api/app/ingest/` — `ingest_chunks` / pipelines call the Strategies (not these helpers by name)
- `api/app/retrieval/` — `search_knowledge(client_id, query, filters?)` → top-k + citations; see `docs/retrieval.md`

All vector-store read/write paths **require** `client_id` (fail closed). Search always applies a payload filter on `client_id`; upsert always stamps `client_id` into the payload.

## Isolation smoke

With Compose Qdrant (+ TEI for the embed probe) up:

```bash
uv run python scripts/qdrant_isolation_smoke.py
```

Expect `isolation_smoke_ok` and `fail_closed_ok missing_client_id`.

## History ingest

See `docs/slack-history-ingest.md` and:

```bash
uv run python scripts/ingest_slack_history.py --client-id <tenant> --format json --path dump.json --query "…"
```
