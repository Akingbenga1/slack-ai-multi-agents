# Task 38.2 — HTTP + worker boundary

**Source:** `Project-Documents/jira-task.md` · `review.md` architecture gap — job-queue

## Steps

- [x] `POST /jobs/...` routes call `JobQueue.enqueue`, not `apply_async` / `worker.tasks` by name
- [x] Upload + workflow library ingest enqueue use `JobQueue`
- [x] Keep `worker/tenant_job.py` and `jobs` table unchanged in behavior
- [x] Thin `worker.tasks.enqueue_*` facades may remain for smoke scripts / Beat internal reuse
- [x] Light smoke: existing job / upload enqueue tests green

## Acceptance criteria

- [x] HTTP job routes call the interface, not `apply_async` directly
- [x] `tenant_job` lifecycle and `jobs` rows unchanged
