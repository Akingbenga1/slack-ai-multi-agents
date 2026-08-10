# Task 29.3 — Dispatcher cleanup

## Steps

- [x] Thin Beat dispatch loops via shared `run_dispatch`
- [x] Extract `build_beat_schedule(settings)` for settings injection (no behavior change)
- [x] Keep Beat entry task names and due-list Strategies unchanged
- [x] Light smoke: dispatch sync + report tests green

## Acceptance criteria

- [x] Dispatchers do not re-implement session/loop boilerplate
- [x] Beat intervals come from injected Settings factory (import-time still uses `get_settings()`)
- [x] No change to enqueue behavior or schedule kind Strategies
