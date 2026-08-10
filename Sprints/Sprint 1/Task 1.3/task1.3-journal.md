# Task 1.3 journal

## Status

`completed`

## Summary

Added `docker-compose.yml` (Postgres 16, Redis 7, Qdrant v1.13.2, TEI cpu-1.6) and `.env.example` with service URLs. Chose open embedding model `BAAI/bge-small-en-v1.5`. `docker compose config` validates. `docker compose up` failed because Docker Desktop engine is not running.

## Acceptance criteria checklist

- [x] Compose defines Postgres, Redis, Qdrant, TEI — done
- [x] TEI uses named open model — done (`BAAI/bge-small-en-v1.5`)
- [x] `.env.example` service URLs — done

## Decision log

- TEI image: `ghcr.io/huggingface/text-embeddings-inference:cpu-1.6` (CPU for laptop-as-VPS).
- Model: `BAAI/bge-small-en-v1.5` — small, open, common for RAG demos.
- Healthchecks included; TEI has long `start_period` for first model download.

## Needs human

None (resolved: Docker Desktop started; `docker compose up -d` healthy).

## Files changed

- `docker-compose.yml`
- `.env.example`
- `README.md` (compose up note already added in 1.2)

## Resume notes

Next batch: Task 1.4 — Health stubs (FastAPI `/health`, Next.js OK page, tunnel plan doc).

## Open questions

None.

## Smoke test results

- `docker compose config` — ok
- `docker compose up -d` — ok (after Docker Desktop started)
- postgres / redis / qdrant / tei — all `healthy`; `/health` on TEI returns 200
