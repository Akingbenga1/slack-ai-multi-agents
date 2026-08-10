# Task 28.2 journal

## Status

`completed`

## Summary

Added `ScheduleKindStrategy` for `slack_history_sync` and `recurring_report` (defaults, normalize/validate, `is_due`). Domain facades + Beat dispatchers use store + strategies; worker imports `list_due_for_kind` / `list_due_recurring_reports`.

## Acceptance criteria checklist

- [x] New schedule kind = Strategy class + registry key
- [x] Validate / defaults / due predicates live on the Strategy
- [x] Beat / dispatchers call store + strategies only

## Decision log

- **Strategy per schedule key** — same pattern family as DeliveryStrategy / ToolStrategy; new kind = class + `SCHEDULE_KIND_STRATEGIES` entry (`review.md` §5.5).
- Service helpers (`read_kind` / `patch_kind` / `patch_schedules`) sit between HTTP and store so routes stay thin.

## Needs human

(none)

## Files changed

- `api/app/schedules/kinds.py` (new)
- `api/app/schedules/service.py` (new)
- `api/app/schedules/__init__.py`
- `api/app/slack/schedule.py`
- `api/app/reports/schedule.py`
- `worker/tasks.py`
- `tests/slack/test_schedule.py`
- `tests/reports/test_schedule.py`
- `tests/slack/test_schedule_api.py`
- `tests/reports/test_post.py`
- `tests/demo/test_first_org_hardening.py`
- `Sprints/Sprint 28/Task 28.2/task28.2.md`

## Resume notes

Continue with Task 28.3 (unified write API + portal).

## Open questions

(none)
