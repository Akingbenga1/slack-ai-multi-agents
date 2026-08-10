# Task 28.4 — Schedule API / Beat tests

## Steps

- [x] Shared fixture factory for schedule blocks (sync + report)
- [x] Collapse twin FakeDB / in-memory store fixtures across slack + reports (+ agent) schedule tests
- [x] Prefer real store + Strategy path in unit list-due tests where FakeDB can seed configs
- [x] Sync + report schedule / Beat tests pass (light smoke)

## Acceptance criteria

- [x] One shared schedule block / FakeDB / memory-schedules helper used by twin modules
- [x] Slack sync + recurring report schedule unit and API tests green
- [x] Beat dispatch smoke (sync + report) still green
