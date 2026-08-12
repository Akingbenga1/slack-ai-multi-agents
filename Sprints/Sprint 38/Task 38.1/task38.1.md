# Task 38.1 — `JobQueue` + Celery adapter

**Source:** `Project-Documents/jira-task.md` · `review.md` architecture gap — job-queue

## Steps

- [x] Define `JobQueue` Strategy: `enqueue(kind, tenant_id, payload)` → vendor-neutral result
- [x] Implement Celery Adapter (owns `apply_async` / task symbols)
- [x] Factory `get_job_queue` via `JOB_QUEUE` (`celery` default; stub other brokers later)
- [x] Keep `REDIS_URL` as the Celery broker — do not rename; Beat interval keys stay
- [x] Beat dispatchers enqueue via `JobQueue`, not Celery-named product helpers
- [x] Keep `@tenant_job` / `jobs` table unchanged
- [x] Update `.env.example`: `JOB_QUEUE`; no new broker URL
- [x] Light smoke: factory + kind routing

## Acceptance criteria

- [x] Product jobs enqueue by `kind` through `JobQueue`; Celery is the first adapter
- [x] Beat schedule entrypoints use the interface for tenant enqueue
- [x] `JOB_QUEUE=celery` selects the adapter; `REDIS_URL` unchanged
