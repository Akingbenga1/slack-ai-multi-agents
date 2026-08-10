# Task 29.2 journal

## Status

`completed`

## Summary

Added `worker/tenant_job.py` with `@tenant_job` / `run_tenant_job` Template Method (session, job meta, running/success/fail, usage). Heartbeat, ingest upload, Slack history sync, and recurring report tasks now only run domain bodies; recurring report keeps `fail_usage_event=EVENT_JOB`.

## Acceptance criteria checklist

- [x] Shared lifecycle shell
- [x] Domain tasks call ingest/sync/report only
- [x] Fail-path usage preserved for recurring report
- [x] Task names / enqueue helpers unchanged

## Decision log

- **Decorator + runner (not inheritance):** `@tenant_job` injects `TenantJobContext` after Celery `self`; payload = kwargs minus lifecycle fields + `celery_task_id`. Matches Sprint 27 function-level Template Method preference.
- Job helpers stay in `job_meta.py`; lifecycle orchestration lives in `tenant_job.py` so tests patch that module.

## Needs human

(none)

## Files changed

- `worker/tenant_job.py` (new)
- `worker/tasks.py`
- `tests/reports/test_failure_logging.py`
- `tests/worker/test_tenant_job.py` (new; also covers 29.3 beat factory)
- `Sprints/Sprint 29/Task 29.2/task29.2.md`

## Resume notes

Continue batch with Task 29.3 (dispatcher cleanup — partially landed with `run_dispatch` used by tasks).

## Open questions

(none)

## Smoke test results

- Failure logging + heartbeat shell tests green
