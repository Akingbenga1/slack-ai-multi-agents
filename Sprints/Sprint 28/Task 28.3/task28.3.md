# Task 28.3 — Align write API with portal

## Steps

- [x] Add single schedules write path under `/agent/schedules` (GET + PATCH)
- [x] Writes go through Strategy validate + `ScheduleStore.upsert_block`
- [x] Update Agent Settings UI to PATCH the unified endpoint
- [x] Keep `/jobs/.../schedule` as thin adapters (same store/strategy path)
- [x] Light smoke: schedule API tests still green; portal uses one write

## Acceptance criteria

- [x] Portal and Beat share Strategy-validated schedule blocks
- [x] Agent Settings saves schedules via one API call
- [x] Legacy job schedule routes still work for existing clients/tests
