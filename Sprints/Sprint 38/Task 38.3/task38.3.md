# Task 38.3 — Tests

**Source:** `Project-Documents/jira-task.md` · Sprint 38 exit

## Steps

- [x] Product HTTP / upload / workflow enqueue surfaces do not call `apply_async` or import Celery / `worker.tasks` enqueue helpers
- [x] Heartbeat, ingest, sync, report enqueue paths still run (API + Beat facades + adapter kind routing)
- [x] Existing job status / usage recording green
- [x] Docs / demo default remain `JOB_QUEUE=celery` + `REDIS_URL` broker
- [x] Sprint 38 exit: replacing Celery with RQ/Dramatiq later is a new adapter, not a rewrite of job kinds or HTTP routes

## Acceptance criteria

- [x] Heartbeat, ingest, sync, report enqueue paths still run
- [x] Existing job status / usage recording green
- [x] Sprint 38 exit met: new broker = new adapter; product kinds / HTTP routes unchanged
