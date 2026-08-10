# Task 17.3 — Celery Beat report task

## Steps

- [x] `post_recurring_report` — prefer channel sync → `run_report` → direct `chat.postMessage`
- [x] Worker `worker.recurring_report` + `enqueue_recurring_report`
- [x] Beat dispatchers for daily / weekly cadence
- [x] Force API `POST /jobs/recurring-report`
- [x] Light tests + docs

## Acceptance criteria

- [x] Prefer sync freshness (non-blocking on sync failure)
- [x] Direct channel post (no draft-approval gate, no thread)
- [x] Forced enqueue works with schedule or body `channel_id`
- [x] Beat lists due tenants (enabled + channel + cadence)
