# Task 29.3 journal

## Status

`completed`

## Summary

Beat dispatchers now use `run_dispatch` (due list → enqueue → response). `build_beat_schedule(settings)` centralizes Beat entries so intervals are Settings-injected; import still wires `get_settings()` once. Docs note the Template Method layout.

## Acceptance criteria checklist

- [x] Thin dispatch loops
- [x] Settings injection via `build_beat_schedule`
- [x] Due-list Strategies / task names unchanged
- [x] Dispatch smoke tests green

## Decision log

- **Shared dispatch helper, not another Strategy layer** — due-list already Strategy-backed (Sprint 28); smell was duplicated session/loop boilerplate only.
- Import-time Beat config retained for zero behavior change; factory enables test/reload without copying the table.

## Needs human

(none)

## Files changed

- `worker/tenant_job.py` (`run_dispatch`)
- `worker/tasks.py` (thin dispatchers)
- `worker/celery_app.py` (`build_beat_schedule`)
- `tests/slack/test_schedule_api.py`
- `tests/reports/test_post.py`
- `tests/worker/test_tenant_job.py`
- `docs/celery.md`
- `Sprints/Sprint 29/Task 29.3/task29.3.md`

## Resume notes

Next: **Continue Sprint 29 from Task 29.4** (worker / ingest regression).

## Open questions

(none)

## Smoke test results

- Dispatch sync + report + beat factory tests green
