# Task 1.3 — Docker Compose services

## Steps

- [x] Add `docker-compose.yml` with Postgres, Redis, Qdrant, TEI
- [x] Choose and document open embedding model for TEI
- [x] Add `.env.example` with service URLs only (no secrets required for Compose)
- [x] Wire Compose to use env defaults from `.env.example` pattern
- [x] Light smoke: `docker compose config` ok; `up` blocked (Docker Desktop not running)

## Acceptance criteria

- [x] Compose defines healthy Postgres, Redis, Qdrant, TEI services
- [x] TEI uses a named open embedding model (`BAAI/bge-small-en-v1.5`)
- [x] `.env.example` lists `DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`, `TEI_URL`
