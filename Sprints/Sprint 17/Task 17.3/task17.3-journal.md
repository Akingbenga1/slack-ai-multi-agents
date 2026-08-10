# Task 17.3 journal

## Status

`completed`

## Summary

Wired Celery Beat + force API for recurring digests. `post_recurring_report` syncs the target channel (best-effort), runs `run_report`, and posts top-level to Slack with no approval gate. Beat entries for daily/weekly cadence; `POST /jobs/recurring-report` for forced posts.

## Acceptance criteria checklist

- [x] Prefer sync freshness
- [x] Direct channel post
- [x] Force enqueue API
- [x] Beat dispatch by cadence

## Decision log

- Sync failure does not block the digest (logged in result.sync).
- Separate Beat intervals for daily vs weekly (configurable seconds).
- Success → `usage_events.report_post`; job row `kind=recurring_report`.

## Needs human

Live verify: configure schedule channel + Slack install + worker/Beat, then `POST /jobs/recurring-report` (or wait for Beat). Inherited Stripe/Slack/Anthropic needs.

## Files changed

- `api/app/reports/post.py`
- `worker/{tasks,celery_app,job_meta}.py`
- `api/app/jobs/routes.py`, `api/app/settings.py`, `.env.example`
- `tests/reports/{test_post,test_schedule_api}.py`
- `docs/celery.md`, `docs/agent.md`, `README.md`
- `Sprints/Sprint 17/Task 17.3/*`

## Resume notes

Next: **Task 17.4 — Failure logging to jobs / usage**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/reports tests/agent/test_report.py -q
→ 23 passed
```

## Commercial mapping

TM-13 — scheduled/forced digest appears in channel (live Slack still Needs human).
