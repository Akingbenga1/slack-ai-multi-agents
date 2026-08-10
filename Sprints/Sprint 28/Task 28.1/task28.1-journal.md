# Task 28.1 journal

## Status

`completed`

## Summary

Extracted shared `ScheduleStore` (`get_block` / `upsert_block` / `list_tenants_for`) on default `AgentConfig.schedules`. Migrated Slack sync + recurring report schedule modules to use it; public facades unchanged.

## Acceptance criteria checklist

- [x] One persistence API for schedule JSONB blocks on default `AgentConfig`
- [x] Slack sync + recurring report modules no longer duplicate upsert/list scaffolding
- [x] Existing `is_*` / `set_*` / `list_tenants_*` call sites keep working

## Decision log

- **Repository-style store** (not full ORM Repository) for the smell of twin JSONB upsert/list loops — matches `review.md` §5.5 / Strategy guidance in patterns doc: extract shared persistence first, kind-specific rules next (28.2).
- Kept `slack.schedule` / `reports.schedule` public names so jobs routes and older imports stay stable.

## Needs human

(none)

## Files changed

- `api/app/schedules/store.py` (new)
- `api/app/schedules/__init__.py` (new)
- `api/app/slack/schedule.py`
- `api/app/reports/schedule.py`
- `Sprints/Sprint 28/Task 28.1/task28.1.md`

## Resume notes

Continue with Task 28.2 in same batch (strategies).

## Open questions

(none)
