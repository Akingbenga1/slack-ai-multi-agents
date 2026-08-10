# Task 28.1 — Shared `ScheduleStore` on `AgentConfig.schedules`

## Steps

- [x] Add `api/app/schedules/store.py` with `get_block` / `upsert_block` / `list_tenants_for`
- [x] Share `DEFAULT_AGENT_NAME` from schedules package
- [x] Migrate `slack/schedule.py` to use the store (public API unchanged)
- [x] Migrate `reports/schedule.py` to use the store (public API unchanged)
- [x] Light smoke: existing schedule unit tests pass

## Acceptance criteria

- [x] One persistence API for schedule JSONB blocks on default `AgentConfig`
- [x] Slack sync + recurring report modules no longer duplicate upsert/list scaffolding
- [x] Existing `is_*` / `set_*` / `list_tenants_*` call sites keep working
