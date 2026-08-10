# Task 28.2 — `ScheduleKindStrategy` for sync + recurring report

## Steps

- [x] Add `ScheduleKindStrategy` protocol + registry (`slack_history_sync`, `recurring_report`)
- [x] Per kind: defaults, validate/normalize, due/list predicates
- [x] Domain schedule modules + Beat list helpers use store + strategies
- [x] Worker dispatchers call store + strategies only (via schedules package)
- [x] Light smoke: schedule unit tests + Beat list filters still pass

## Acceptance criteria

- [x] New schedule kind = Strategy class + registry key
- [x] Validate / defaults / due predicates live on the Strategy, not twin schedule modules
- [x] Beat / dispatchers do not reimplement block reads
