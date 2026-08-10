# Slack Web API client (live history)

Used by Sprint 9 live sync to list channels and pull messages with the install-store bot token.

## Client

```python
from api.app.slack.client import (
    SlackWebClient,
    slack_client_for_tenant,
    slack_client_for_team,
)

# From install store (preferred)
client = slack_client_for_tenant(db, settings, tenant_id)
# or: slack_client_for_team(db, settings, team_id)

for channel in client.conversations_list():
    channel_id = channel["id"]
    for raw in client.conversations_history(channel_id, oldest=watermark_ts):
        ...
```

Direct token (tests / scripts):

```python
client = SlackWebClient(bot_token="xoxb-…")
```

## Behaviour

- Methods: `conversations.list`, `conversations.history` (cursor pagination); Sprint 23 also `files.info`, private URL download, `files.upload` (POST multipart), `files.edit` (title best-effort for rename).
- On HTTP **429** or JSON `error=ratelimited`, sleeps `Retry-After` (default 1s) and retries up to `max_retries` (default 5).
- Exhausted retries → `SlackRateLimitError`; other `ok=false` → `SlackApiError`.
- Token comes from Fernet-encrypted `slack_installs.bot_token_encrypted` via `get_bot_token`.

File download/upload details: `docs/slack-file-actions.md`.

## Normalize for ingest

```python
from api.app.ingest import SourceFormat, normalize_slack_message

msg = normalize_slack_message(
    raw,
    channel=channel_id,
    source_format=SourceFormat.WEB_API,
)
```

## Watermarks (Postgres)

Per-channel cursors live in `sync_watermarks` (`source=slack_live`):

```python
from api.app.slack.watermarks import (
    bounds_from_watermark,
    get_watermark,
    upsert_watermark,
)

row = get_watermark(db, tenant_id=tenant_id, channel_id="C012")
oldest, latest = bounds_from_watermark(row)
# Incremental pull: conversations_history(channel, oldest=latest)

upsert_watermark(
    db,
    tenant_id=tenant_id,
    channel_id="C012",
    oldest=first_ts,   # bootstrap lower bound (kept as min)
    latest=last_ts,    # high-water (advanced as max); also stored in `cursor`
)
```

### Celery sync

```python
from worker.tasks import enqueue_slack_history_sync

enqueue_slack_history_sync(client_id=str(tenant_id))  # optional channel_ids=[...]
```

Domain helper: `api.app.slack.sync.sync_slack_history` (list → history with watermark → `WEB_API` normalize → `ingest_messages` → upsert watermark).

**Beat:** hourly `worker.dispatch_slack_history_syncs` enqueues sync for tenants with a Slack install when `agent_configs.schedules.slack_history_sync.enabled` is not false (default on). Toggle via `GET`/`PATCH /jobs/slack-history-sync/schedule`. **On-demand:** `POST /jobs/slack-history-sync` (auth required; bypasses enable flag). **Status:** `GET /jobs/slack-history-sync/status` (last success/failure + watermarks). See `docs/celery.md`.

## Scopes

See `docs/slack-app-setup.md` — history sync needs `channels:*` / `groups:*` and a workspace reinstall if scopes changed after first install.

## Tests

```bash
uv run pytest tests/slack -q
```
