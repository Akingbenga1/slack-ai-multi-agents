# Task 19.1 journal

## Status

`completed`

## Summary

Added `GET`/`PATCH /agent/config` and `/app/agent` UI for display name, system prompt, channel allowlist, plus schedule toggles via existing jobs APIs. Org prompt overlays compose when set.

## Acceptance criteria checklist

- [x] Name / prompt / allowlist self-serve
- [x] Schedules enable/disable on same page
- [x] Cross-tenant denied
- [x] OR-03 / OR-04

## Decision log

- Display name in `extra.display_name` so row key stays `name=default` (schedule lookups).
- Allowlist shape `{"channels": [...]}`; empty = unrestricted stored.
- Schedules still patched via `/jobs/.../schedule` (reuse Sprint 9/17 APIs).

## Needs human

None new (inherited Slack/Stripe). Portal smoke: sign in as org admin → `/app/agent`.

## Files changed

- `api/app/agent/config_store.py`, `routes.py`, `run.py`, `nodes/compose.py`, `state.py`
- `web/app/app/agent/page.tsx`, `components/AgentSettingsPanel.tsx`, `OrgNav.tsx`
- `tests/agent/test_config_api.py`
- `docs/portal.md`, `docs/agent.md`
- `Sprints/Sprint 19/Task 19.1/*`

## Resume notes

Next in batch: **Task 19.2**.

## Smoke test results

```
uv run pytest tests/agent/test_config_api.py -q
→ passed (with batch)
```

## Commercial mapping

OR-03 / OR-04 — org self-serve agent management.
