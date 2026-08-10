# Qdrant + TEI (Sprint 6+)

Vector store and embeddings for tenant knowledge. Sprint 6: collection + fail-closed helpers + TEI client. Sprint 7: Slack history ingest pipeline on top.

## Config

| Setting | Env | Default |
| ------- | --- | ------- |
| Qdrant URL | `QDRANT_URL` | `http://localhost:6333` |
| Collection | `QDRANT_COLLECTION` | `knowledge` |
| TEI URL | `TEI_URL` | `http://localhost:8080` |
| Model id | `EMBEDDING_MODEL_ID` | `BAAI/bge-small-en-v1.5` |
| Vector size | `EMBEDDING_DIM` | `384` |

Compose TEI must use the same `--model-id` (see `docker-compose.yml`).

## Modules

- `api/app/qdrant/` — `ensure_knowledge_collection()`, `upsert_vectors()`, `search_vectors()`
- `api/app/tei/` — `TeiClient.embed()` → `POST {TEI_URL}/embed`
- `api/app/ingest/pipeline.py` — chunk → embed → upsert (idempotent point ids)
- `api/app/retrieval/` — `search_knowledge(client_id, query, filters?)` → top-k + citations (Sprint 10); see `docs/retrieval.md`

All Qdrant read/write helpers **require** `client_id` (fail closed). Search always applies a payload filter on `client_id`; upsert always stamps `client_id` into the payload. `search_vectors` accepts optional `extra_conditions` AND'd with the tenant filter.

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
