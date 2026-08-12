# Celery queues (Sprint 5; Sprint 38 JobQueue)

Background jobs use **Celery + Redis** on the laptop-VPS via the ``JobQueue``
Strategy (`JOB_QUEUE=celery` demo default). Product code enqueues by ``kind``
through ``get_job_queue().enqueue(...)`` — it does not call ``apply_async`` by
name. App processes run on the host; Redis is the Compose service at
`REDIS_URL` (default `redis://localhost:6379/0`). Do not rename `REDIS_URL`.

## Run Worker + Beat

From the repo root (after `uv sync`, `docker compose up -d`, and `.env` with `REDIS_URL` / `DATABASE_URL`):

```bash
# Worker — consume high, default, and low queues
# Windows: add --pool=solo (prefork is unsupported)
uv run celery -A worker.celery_app worker --loglevel=INFO -Q high,default,low --pool=solo

# Beat — schedules (separate process; required for periodic heartbeat)
uv run celery -A worker.celery_app beat --loglevel=INFO
```

On Linux/macOS you can omit `--pool=solo` (default prefork).
Optional one-shot smoke (enqueue + wait; worker must be running):

```bash
uv run python -c "from worker.tasks import enqueue_heartbeat; from api.app.membership import DEMO_TENANT_ID; r=enqueue_heartbeat(client_id=str(DEMO_TENANT_ID)); print(r.id)"
```

## Queue names

| Queue | When used |
| ----- | --------- |
| `high` | `priority >= 10` (urgent / on-demand) |
| `default` | normal work (`0 <= priority < 10`), including Beat heartbeat |
| `low` | `priority <= -1` (bulk / background) |

Routing helpers: `worker.queues.queue_for_priority`, `worker.queues.enqueue_options` (sets queue + `client_id` task header).

Tenant isolation on jobs is via **`client_id` headers** (and Postgres `jobs.tenant_id`), not one Redis queue per tenant. Priority queues keep noisy bulk work from starving urgent tasks across the 1–3 client demo.

## Beat schedule

| Name | Task | Interval | Tenant / scope |
| ---- | ---- | -------- | -------------- |
| `demo-tenant-heartbeat` | `worker.heartbeat` | 60s | demo org `11111111-1111-1111-1111-111111111111` |
| `slack-history-sync-hourly` | `worker.dispatch_slack_history_syncs` | 1h (configurable) | all tenants with Slack install + sync enabled |
| `recurring-report-daily` | `worker.dispatch_recurring_reports` | 24h (configurable) | enabled report schedules with `cadence=daily` |
| `recurring-report-weekly` | `worker.dispatch_recurring_reports` | 7d (configurable) | enabled report schedules with `cadence=weekly` |

Heartbeat writes a row to Postgres `jobs` (`kind=heartbeat`) and logs with `client_id=…`.

## Job lifecycle Template Method (Sprint 29)

Tenant Celery tasks (`heartbeat`, `ingest_upload`, `slack_history_sync`, `recurring_report`) share **`worker/tenant_job.py`**:

- `@tenant_job(kind=…, usage_event=…)` / `run_tenant_job` — resolve tenant → session → create/running → domain body → succeed + usage (or fail + optional fail usage)
- `run_dispatch` — thin Beat loops (due list → enqueue)
- `build_beat_schedule(settings)` in `worker/celery_app.py` — intervals from Settings (factory; import still uses `get_settings()` once)

Domain bodies only call `ingest_upload` / `sync_slack_history` / `post_recurring_report`. Shared embed + upsert for knowledge ingest lives in `api.app.ingest.chunks_ingest.ingest_chunks` (Slack message vs document supply `point_id_fn` / `payload_fn`; adapters via `EMBEDDING_PROVIDER` / `VECTOR_STORE`).

## Upload ingest (Sprint 8)

Task name: `worker.ingest_upload` (`kind=ingest_upload` in `jobs`).

Triggered by `POST /uploads` (default `enqueue=true`). Parses `file_role=document|slack_history`, then chunk → embed → upsert. See `docs/uploads.md` and `docs/document-ingest.md`.

## Live Slack history sync (Sprint 9)

Task name: `worker.slack_history_sync` (`kind=slack_history_sync` in `jobs`).

Pulls `conversations.list` / `conversations.history` with the install-store token, normalizes as `source_format=web_api`, ingests via the same pipeline, and advances per-channel watermarks. Default enqueue priority `-1` (low queue). See `docs/slack-web-api.md`.

```bash
uv run python -c "from worker.tasks import enqueue_slack_history_sync; from api.app.membership import DEMO_TENANT_ID; r=enqueue_slack_history_sync(client_id=str(DEMO_TENANT_ID)); print(r.id)"
```

### Beat (hourly) + per-tenant enable

| Name | Task | Interval | Behaviour |
| ---- | ---- | -------- | --------- |
| `slack-history-sync-hourly` | `worker.dispatch_slack_history_syncs` | `SLACK_HISTORY_SYNC_INTERVAL_SECONDS` (default **3600**) | Enqueues sync for each tenant that has a Slack install and is not disabled |

Enable/disable is stored on `agent_configs.schedules.slack_history_sync.enabled` (default **true** when unset). Disabled tenants are skipped by Beat; **on-demand enqueue still works**.

### On-demand API (Task 9.4)

```bash
# Token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Enqueue live sync for the caller's tenant
curl -s -X POST http://localhost:8000/jobs/slack-history-sync \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{}'

# Read / toggle Beat enable for the tenant (preferred unified API)
curl -s http://localhost:8000/agent/schedules \
  -H "Authorization: Bearer $TOKEN"
curl -s -X PATCH http://localhost:8000/agent/schedules \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"slack_history_sync":{"enabled":false}}'
# Legacy adapters still work:
curl -s -X PATCH http://localhost:8000/jobs/slack-history-sync/schedule \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"enabled":false}'
```

Enqueue response: `{ "task_id", "client_id", "queue", "kind": "slack_history_sync" }`. Unauthenticated → 401; cross-tenant → 403.

### Sync status API (Task 9.5)

```bash
curl -s http://localhost:8000/jobs/slack-history-sync/status \
  -H "Authorization: Bearer $TOKEN"
```

Response includes `enabled`, `slack_connected`, `last_success` / `last_failure` / `last_job` (job snapshots), and `watermarks` (`channel_count`, `last_synced_at`).

## Recurring report schedule (Sprint 17.2)

Stored on `agent_configs.schedules.recurring_report`:

| Field | Default | Purpose |
| ----- | ------- | ------- |
| `enabled` | `false` | Beat include/exclude (opt-in) |
| `channel_id` | `null` | Slack channel for **direct** posts (required when enabled for Beat) |
| `cadence` | `weekly` | `daily` or `weekly` |
| `window_label` | derived | Digest window (`last 24 hours` / `last 7 days`) |

```bash
# Preferred: unified agent schedules API
curl -s http://localhost:8000/agent/schedules \
  -H "Authorization: Bearer $TOKEN"
curl -s -X PATCH http://localhost:8000/agent/schedules \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"recurring_report":{"enabled":true,"channel_id":"C01234567","cadence":"weekly"}}'
# Legacy adapter:
curl -s -X PATCH http://localhost:8000/jobs/recurring-report/schedule \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"enabled":true,"channel_id":"C01234567","cadence":"weekly"}'
```

Helpers: `api.app.schedules` (`ScheduleStore` + `ScheduleKindStrategy`); facades in `api.app.reports.schedule` / `api.app.slack.schedule`. Beat dispatchers call `list_due_for_kind` / `list_due_recurring_reports`.

**Add a schedule kind:** implement `ScheduleKindStrategy` (defaults / normalize / apply_patch / is_due) → register on `SCHEDULE_KIND_STRATEGIES` in `api/app/schedules/kinds.py` → optional thin facade under `slack/` or `reports/`. Portal + Beat already share `GET`/`PATCH /agent/schedules` and the store. Shared test blocks: `tests/schedules/helpers.py` (`sync_block` / `report_block` / `FakeScheduleDB` / `MemorySchedules`).

### Force post + Beat (Task 17.3)

| Name | Task | Interval | Behaviour |
| ---- | ---- | -------- | --------- |
| `recurring-report-daily` | `worker.dispatch_recurring_reports` | `RECURRING_REPORT_DAILY_INTERVAL_SECONDS` (default **86400**) | Enqueues for enabled tenants with `cadence=daily` + channel |
| `recurring-report-weekly` | `worker.dispatch_recurring_reports` | `RECURRING_REPORT_WEEKLY_INTERVAL_SECONDS` (default **604800**) | Same for `cadence=weekly` |

Worker task `worker.recurring_report` (`kind=recurring_report`): optional channel sync for freshness → `run_report` → **direct** `chat.postMessage` (no draft approval, top-level message). Records `report_post` usage; failures mark the `jobs` row failed.

```bash
# Force a report now (uses saved channel_id, or pass channel_id in body)
curl -s -X POST http://localhost:8000/jobs/recurring-report \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"channel_id":"C01234567","prefer_sync":true}'
```

## API trigger stub (Task 5.4)

Auth-required heartbeat enqueue (does not wait for the worker):

```bash
# Token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Enqueue heartbeat for the caller's tenant (org_admin) or X-Client-Id / body.tenant_id (platform_owner)
curl -s -X POST http://localhost:8000/jobs/heartbeat \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"message":"api-stub"}'
```

Response: `{ "task_id", "client_id", "queue", "kind": "heartbeat" }`. Unauthenticated → 401; cross-tenant → 403.
