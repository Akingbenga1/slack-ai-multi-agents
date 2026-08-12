# Task 38.2 journal

## Status

`completed`

## Summary

Wired `POST /jobs/*`, portal uploads, and workflow-library ingest enqueue through `get_job_queue().enqueue`. Routes no longer import `worker.tasks` enqueue helpers or `apply_async`. `@tenant_job` / `jobs` table unchanged. Marked job-queue gap Implemented in `review.md`.

## Acceptance criteria checklist

- [x] HTTP job routes call the interface, not `apply_async` directly
- [x] `tenant_job` lifecycle and `jobs` rows unchanged

## Decision log

- **Route boundary:** jobs + uploads import `get_job_queue` + kind constants from `worker.job_meta` (product kinds), not Celery task symbols.
- **Tests:** monkeypatches now fake `get_job_queue` / return `EnqueueResult` instead of `AsyncResult`-like objects.

## Needs human

None new.

## Files changed

- `api/app/jobs/routes.py`
- `api/app/uploads/routes.py`
- `api/app/workflows/library.py`
- `tests/uploads/test_upload_api.py`
- `tests/slack/test_schedule_api.py`
- `tests/reports/test_schedule_api.py`
- `tests/reports/test_post.py`
- `docs/celery.md`
- `Project-Documents/review.md`

## Smoke test results

- `uv run pytest tests/job_queue/ tests/uploads/test_upload_api.py tests/slack/test_schedule_api.py tests/reports/test_schedule_api.py tests/reports/test_post.py tests/worker/test_tenant_job.py -q` → **33 passed**

## Resume notes

Next Ralph batch: **Continue Sprint 38 from Task 38.3** — Tests (Sprint 38 exit).

## Open questions

None.
