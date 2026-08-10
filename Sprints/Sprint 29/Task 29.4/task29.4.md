# Task 29.4 — Worker / ingest regression

**Sprint:** 29 — Ingest core + worker Template Method  
**Source:** `Project-Documents/jira-task.md` Task 29.4; `review.md` §5.6–5.7 / P5

## Steps

- [x] Confirm tenant Celery tasks use `@tenant_job` only (no duplicated session/job/usage blocks)
- [x] Confirm Beat dispatchers use `run_dispatch` only
- [x] Confirm Slack + document ingest call shared `ingest_chunks` (no duplicate TEI/upsert loops)
- [x] Run ingest test suite (chunks, pipeline, upload, parsers, formats)
- [x] Run worker / job-related tests (`test_tenant_job`, failure logging, schedule/dispatch, reports post)
- [x] Fix any regressions from Sprint 29 refactors
- [x] Light smoke: import paths + task names unchanged
- [x] Static guards: no lifecycle leak in `worker/tasks.py`; pipelines delegate upsert to `ingest_chunks`

## Acceptance criteria

- [x] Existing ingest + job tests green
- [x] No duplicate lifecycle blocks in new/refactored tasks
- [x] Sprint 29 exit: new Celery task need not copy job boilerplate; embed/upsert bugs fixed in one place

## Notes

Regression-only task — no new product features. Pattern choices already logged in 29.1–29.3 journals.
