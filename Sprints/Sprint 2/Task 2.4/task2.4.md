# Task 2.4 — Deep health checks

## Steps

- [x] Probe Postgres (SELECT 1)
- [x] Probe Redis (PING)
- [x] Probe Qdrant (`/readyz`)
- [x] Probe TEI (`/health`)
- [x] Return aggregated `/health` with per-check status

## Acceptance criteria

- [x] `/health` reports postgres, redis, qdrant, tei
- [x] Overall status ok when all dependencies healthy
