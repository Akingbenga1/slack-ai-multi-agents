# Task 17.4 journal

## Status

`completed`

## Summary

Confirmed recurring report failures mark the `jobs` row failed and emit a `job` usage event (`kind=recurring_report`, `status=failed`). Success path already records `report_post` (17.3). Added a focused failure-path unit test.

## Acceptance criteria checklist

- [x] Failed jobs row
- [x] Failure usage event
- [x] Success `report_post` unchanged

## Decision log

- Failure usage uses `EVENT_JOB` (not `report_post`) so budgets distinguish posts vs errors.
- Implemented inside `worker.recurring_report` (no separate logger module).

## Needs human

Live Slack force/schedule post still needed for Sprint 17 exit (“report appears in the right channel”).

## Files changed

- `worker/tasks.py` (failure usage already from 17.3; verified)
- `tests/reports/test_failure_logging.py`
- `docs/governance.md`, `docs/agent.md`
- `Sprints/Sprint 17/Task 17.4/*`

## Resume notes

Sprint 17 complete. Next: **Continue Sprint 18 from Task 18.1**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/reports tests/agent/test_report.py -q
→ 23 passed
```

## Commercial mapping

OR-07 / TM-13 — failed proactive posts observable in jobs/usage.
