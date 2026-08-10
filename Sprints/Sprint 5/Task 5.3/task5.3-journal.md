# Task 5.3 journal

## Status

`completed`

## Summary

`worker.heartbeat` creates/updates Postgres `jobs` for the tenant, logs `client_id=…`, and Beat schedule `demo-tenant-heartbeat` fires every 60s for the demo org. Sprint 5 exit (Beat fires; worker logs heartbeat with `client_id`) verified on laptop-VPS.

## Acceptance criteria checklist

- [x] Persist `jobs` row — done (`worker/job_meta.py`)
- [x] Logs include `client_id` — done (message text; Celery overrides root handlers)
- [x] Beat fires — done (`Scheduler: Sending due task demo-tenant-heartbeat`)

## Decision log

- Job statuses: `pending` | `running` | `succeeded` | `failed`.
- Kind: `heartbeat`. Demo Beat target: `DEMO_TENANT_ID`.
- `enqueue_heartbeat()` helper for API (Task 5.4).

## Needs human

None for this task. (Sprint 4 Slack live verify still open at project level.)

## Files changed

- `worker/tasks.py`, `worker/job_meta.py`, `worker/celery_app.py` (beat_schedule)
- `docs/celery.md`

## Resume notes

Next batch: Task 5.4 — API trigger stub (auth-required enqueue heartbeat).

## Open questions

None.

## Smoke test results

- Manual enqueue → `succeeded` job + result with `client_id`
- Beat → worker log: `heartbeat start … client_id=11111111-1111-1111-1111-111111111111`
