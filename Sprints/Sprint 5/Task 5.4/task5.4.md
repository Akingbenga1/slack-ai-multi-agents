# Task 5.4 — API trigger stub

## Steps

- [x] Add auth-required FastAPI endpoint to enqueue `worker.heartbeat` for a tenant
- [x] Resolve tenant via JWT + `X-Client-Id` / body (reject cross-tenant for org_admin)
- [x] Return Celery `task_id` (+ client_id / queue) without waiting for completion
- [x] Document endpoint in README / `docs/celery.md`

## Acceptance criteria

- [x] Unauthenticated request → 401
- [x] Org admin cannot enqueue for another tenant → 403
- [x] Authenticated enqueue returns `task_id`; worker can pick up heartbeat with `client_id`
