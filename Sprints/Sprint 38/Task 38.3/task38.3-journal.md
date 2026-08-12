# Task 38.3 journal

## Status

`completed`

## Summary

Locked Sprint 38 exit with JobQueue isolation + enqueue regression: product HTTP / upload / workflow paths stay on `get_job_queue().enqueue`; `apply_async` stays in `CeleryJobQueue`. Added heartbeat API smoke, adapter kind-routing coverage for all four product kinds, and source isolation scans. Job status + usage suites green. Demo default remains `JOB_QUEUE=celery` + `REDIS_URL`.

## Acceptance criteria checklist

- [x] Heartbeat, ingest, sync, report enqueue paths still run
- [x] Existing job status / usage recording green
- [x] Sprint 38 exit met: new broker = new adapter; product kinds / HTTP routes unchanged

## Decision log

- **Isolation scan:** mirrors Sprint 35–37 — forbid `apply_async` / Celery / `worker.tasks` imports on product enqueue modules; require `get_job_queue` + `.enqueue(`.
- **Heartbeat API gap:** no prior `/jobs/heartbeat` TestClient coverage; added `tests/jobs/test_heartbeat_api.py` so all four enqueue surfaces have HTTP smokes.
- **Payload field `celery_task_id`:** left as historical jobs-payload key on ingest status (not an enqueue boundary leak).

## Needs human

None new.

## Files changed

- `tests/job_queue/test_job_queue_isolation.py` (new)
- `tests/job_queue/test_celery_adapter_kinds.py` (new)
- `tests/jobs/test_heartbeat_api.py` (new)
- `api/app/jobs/routes.py` (docstrings: enqueue task id, not Celery)
- `api/app/uploads/routes.py` (UploadResponse task_id description)
- `Sprints/Sprint 38/Task 38.3/task38.3.md`

## Smoke test results

- `uv run pytest tests/job_queue/ tests/jobs/test_heartbeat_api.py tests/uploads/test_upload_api.py tests/uploads/test_ingest_status.py tests/slack/test_schedule_api.py tests/slack/test_sync_status.py tests/reports/test_schedule_api.py tests/reports/test_post.py tests/worker/test_tenant_job.py tests/governance/test_usage.py tests/governance/test_budgets.py -q` → **55 passed**

## Resume notes

**Sprint 38 complete.** Next Ralph batch: **Continue Sprint 39 from Task 39.1** — `AgentRuntime` adapter.

## Open questions

None.
