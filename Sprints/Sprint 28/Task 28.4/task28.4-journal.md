# Task 28.4 journal

## Status

`completed`

## Summary

Collapsed twin schedule fixtures into `tests/schedules/helpers.py` (`sync_block` / `report_block`, `FakeScheduleDB`, `MemorySchedules`). Slack + report unit/API tests and agent schedules API now share that factory; list-due tests seed real store blocks instead of monkeypatching `get_block`. Docs note how to add a schedule kind.

## Acceptance criteria checklist

- [x] One shared schedule block / FakeDB / memory-schedules helper used by twin modules
- [x] Slack sync + recurring report schedule unit and API tests green
- [x] Beat dispatch smoke (sync + report) still green

## Decision log

- **Shared fixture factory** (not another Strategy layer) — matches `review.md` §5.9: one block factory after store unification; API fakes use kind Strategies for normalize/patch so validation stays single-sourced.
- Kept domain test modules (`tests/slack`, `tests/reports`) rather than merging into one file — same helpers, clear product ownership.

## Needs human

(none)

## Files changed

- `tests/schedules/helpers.py` (new)
- `tests/schedules/__init__.py` (new)
- `tests/schedules/test_helpers.py` (new)
- `tests/slack/test_schedule.py`
- `tests/slack/test_schedule_api.py`
- `tests/reports/test_schedule.py`
- `tests/reports/test_schedule_api.py`
- `tests/agent/test_schedules_api.py`
- `tests/reports/test_post.py`
- `tests/demo/test_first_org_hardening.py`
- `docs/celery.md`, `docs/agent.md`
- `Sprints/Sprint 28/Task 28.4/task28.4.md`

## Resume notes

Sprint 28 complete. Next: **Continue Sprint 29 from Task 29.1**.

## Open questions

(none)

## Smoke test results

- 29 passed (schedule unit/API + helpers + Beat dispatch + demo entitlement list)
