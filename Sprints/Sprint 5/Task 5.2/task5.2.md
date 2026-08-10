# Task 5.2 — Tenant/priority queues

## Steps

- [x] Define named queues (`high` / `default` / `low`) and priority → queue mapping
- [x] Route enqueues by priority; attach `client_id` task headers
- [x] Document queue names for operators

## Acceptance criteria

- [x] Queue names documented
- [x] Helpers route by `priority` and carry `client_id` (tenant context)
- [x] Worker consumes all three queues (`-Q high,default,low`)
