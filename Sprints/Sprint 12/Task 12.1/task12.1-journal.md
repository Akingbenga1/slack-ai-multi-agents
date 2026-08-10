# Task 12.1 journal

## Status

`completed`

## Summary

Added Redis fixed-window per-tenant RPM at the API gateway (`TenantRateLimitMiddleware`) keyed by `client_id`. Slack Events apply the same counter after install→tenant resolve (200 + skip work, not 429). Docs in `docs/governance.md`.

## Acceptance criteria checklist

- [x] Over RPM → blocked (429 on API; Slack soft-block)
- [x] Isolated by `client_id`
- [x] Redis down → fail open; no client_id → skip

## Decision log

- Fixed 60s windows (simple RPM) rather than sliding window.
- Slack returns 200 when limited to avoid Events retry storms.
- Fail open on Redis errors so laptop-VPS stays usable if Redis blips.

## Needs human

None new (uses existing Redis).

## Files changed

- `api/app/governance/rate_limit.py`, `__init__.py`
- `api/app/middleware.py`, `main.py`, `settings.py`
- `api/app/slack/routes.py`
- `tests/governance/test_rate_limit.py`
- `docs/governance.md`, `.env.example`, `README.md`
- `Sprints/Sprint 12/Task 12.1/*`

## Resume notes

Next in batch: **Task 12.2 — Token/job budgets from plan**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/governance -q  → 10 passed
```
