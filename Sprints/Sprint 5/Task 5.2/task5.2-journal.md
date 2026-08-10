# Task 5.2 journal

## Status

`completed`

## Summary

Named priority queues `high` / `default` / `low` with `queue_for_priority` + `enqueue_options` (queue + `client_id` header). Documented in `docs/celery.md`. Tenant isolation stays on headers + `jobs.tenant_id`, not one Redis queue per tenant.

## Acceptance criteria checklist

- [x] Queue names documented — done
- [x] Route by priority + client_id — done (`worker/queues.py`)
- [x] Worker `-Q high,default,low` — done (README / docs)

## Decision log

- Priority thresholds: `>= 10` → high, `<= -1` → low, else default.
- No per-tenant Redis queues at 1–3 client scale; headers + DB scope isolation.

## Needs human

None.

## Files changed

- `worker/queues.py` (new)
- `docs/celery.md`, `README.md`

## Resume notes

Task 5.3 heartbeat + jobs persistence (same batch).

## Open questions

None.
