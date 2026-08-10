# Task 28.3 journal

## Status

`completed`

## Summary

Added `GET`/`PATCH /agent/schedules` (Strategy-validated, store-backed). Agent Settings portal now saves sync + report in one PATCH. Legacy `/jobs/.../schedule` routes remain as thin adapters. Docs updated.

## Acceptance criteria checklist

- [x] Portal and Beat share Strategy-validated schedule blocks
- [x] Agent Settings saves schedules via one API call
- [x] Legacy job schedule routes still work for existing clients/tests

## Decision log

- Preferred **`/agent/schedules`** over `/jobs/schedules` so portal config stays under agent settings; jobs routes stay enqueue/status-focused.
- Did **not** split `jobs/routes.py` — still manageable; Strategy lives in `schedules.kinds`, not in the router.

## Needs human

(none)

## Files changed

- `api/app/agent/routes.py`
- `api/app/agent/config_store.py`
- `web/components/AgentSettingsPanel.tsx`
- `tests/agent/test_schedules_api.py` (new)
- `docs/agent.md`, `docs/portal.md`, `docs/slack-web-api.md`, `docs/celery.md`
- `Sprints/Sprint 28/Task 28.3/task28.3.md`

## Resume notes

Next batch: **Continue Sprint 28 from Task 28.4** (collapse twin schedule fixtures; sync + report schedule tests pass).

## Open questions

(none)

## Smoke test results

- Schedule unit + API + agent schedules + related: 36 passed (incl. prior 32 + 4 agent)
