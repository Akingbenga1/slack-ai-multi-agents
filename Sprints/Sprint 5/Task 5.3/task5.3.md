# Task 5.3 — Heartbeat task + job metadata

## Steps

- [x] Implement `worker.heartbeat` with tenant `client_id` context
- [x] Persist run status in Postgres `jobs` (`pending` → `running` → `succeeded`/`failed`)
- [x] Beat schedule demo-tenant heartbeat every 60s

## Acceptance criteria

- [x] Heartbeat writes `jobs` row (`kind=heartbeat`) for tenant
- [x] Worker logs include `client_id`
- [x] Beat fires scheduled heartbeat (Sprint 5 exit)
