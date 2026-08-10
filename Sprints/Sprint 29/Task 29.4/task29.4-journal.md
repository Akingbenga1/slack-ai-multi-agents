# Task 29.4 journal

## Status

`completed`

## Summary

Regression confirmed for Sprint 29 ingest + worker Template Method work. Existing ingest/worker/job suites green (51 tests in the regression set). Static guards lock exit criteria: `worker/tasks.py` must not reintroduce job lifecycle boilerplate; Slack/document pipelines must not call `upsert_vectors` directly.

## Acceptance criteria checklist

- [x] Existing ingest + job tests green
- [x] No duplicate lifecycle blocks in refactored tasks
- [x] Sprint 29 exit met (boilerplate in `@tenant_job` / `run_dispatch`; embed/upsert in `ingest_chunks`)

## Decision log

- **Static source guards over deeper integration QA** — light smoke only; two file-content assertions document the exit criteria for future Celery/ingest tasks without over-testing.

## Needs human

(none)

## Files changed

- `tests/worker/test_tenant_job.py` (29.4 regression guards)
- `Sprints/Sprint 29/Task 29.4/task29.4.md`

## Resume notes

Sprint 29 complete. Next: **Continue Sprint 30 from Task 30.1**

## Open questions

(none)

## Smoke test results

- `tests/ingest` + worker/job-related: 51 passed
- New guards + focused re-run: 15 passed
