# Task 38.1 journal

## Status

`completed`

## Summary

Introduced `JobQueue` Strategy + `get_job_queue` Factory and `CeleryJobQueue` Adapter. Product enqueue is `enqueue(kind, tenant_id, payload)` → `EnqueueResult`. Beat dispatchers and thin `worker.tasks.enqueue_*` facades go through the Strategy. `REDIS_URL` stays the Celery broker; `@tenant_job` / `jobs` unchanged.

## Acceptance criteria checklist

- [x] Product jobs enqueue by `kind` through `JobQueue`; Celery is the first adapter
- [x] Beat schedule entrypoints use the interface for tenant enqueue
- [x] `JOB_QUEUE=celery` selects the adapter; `REDIS_URL` unchanged

## Decision log

- **Patterns:** Strategy (`JobQueue`) + Factory (`JOB_QUEUE`) + Adapter (`CeleryJobQueue`).
- **`EnqueueResult.id`:** alias for historical `AsyncResult.id` callers / smoke scripts.
- **Slack sync default priority:** when payload omits `priority`, adapter uses `-1` (low queue) to match prior helper default.
- **Thin facades:** `worker.tasks.enqueue_*` remain for docs/smokes; Beat uses `get_job_queue` directly.

## Needs human

None new.

## Files changed

- `api/app/job_queue/` (`provider.py`, `celery_adapter.py`, `types.py`, `__init__.py`)
- `api/app/settings.py` (`job_queue`)
- `.env.example` (`JOB_QUEUE`)
- `worker/tasks.py` (facades + Beat dispatchers)
- `tests/job_queue/test_job_queue_factory.py`
- `docs/celery.md`
- `Project-Documents/review.md` (partial — completed with 38.2)

## Smoke test results

- Covered with Task 38.2 suite (see 38.2 journal).

## Resume notes

Continue Task 38.2 — HTTP + worker boundary (same batch).

## Open questions

None.
