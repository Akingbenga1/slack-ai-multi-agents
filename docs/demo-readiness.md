# Demo readiness (Sprint 22.1)

First-org hardening helpers so a **single demo organisation** can be proven end-to-end with fixtures/mocks. Live Stripe / Slack / Anthropic remain **Needs human** (see `Sprints/progress.md`).

## Demo tenant

| Item | Value |
| ---- | ----- |
| Tenant id | `11111111-1111-1111-1111-111111111111` (`DEMO_TENANT_ID`) |
| Org admin | `admin@example.com` / `admin123` → `/app` |
| Platform owner | `owner@example.com` / `owner123` → `/admin` |

Prefer this id for smoke CLIs (`agent_dry_run`, history ingest, etc.) so knowledge lands on the portal org.

## Seed env (optional)

| Variable | Purpose |
| -------- | ------- |
| `DEMO_ACTIVATE_PLAN` | When `true`, seed sets `plan_status=active` + entitlements (no Checkout) |
| `DEMO_SLACK_TEAM_ID` | Optional fixture workspace id |
| `DEMO_SLACK_BOT_TOKEN` | Optional bot token (encrypted into `slack_installs`) |
| `DEMO_REPORT_CHANNEL_ID` | Optional channel; enables weekly recurring report schedule |

```bash
# .env
DEMO_ACTIVATE_PLAN=true
# DEMO_SLACK_TEAM_ID=T_DEMO
# DEMO_SLACK_BOT_TOKEN=xoxb-…
# DEMO_REPORT_CHANNEL_ID=C…

uv run python scripts/seed_demo.py
uv run python scripts/first_org_hardening_smoke.py
uv run pytest tests/demo/test_first_org_hardening.py -q
```

## Entitlement gates

Unpaid / inactive tenants are denied:

- Slack agent replies (`agent`) — existing copy
- `POST /jobs/slack-history-sync` (`sync` + active plan budget)
- `POST /uploads` when enqueueing ingest (`ingest`)
- `POST /jobs/recurring-report` (`agent`)
- Celery Beat sync / report due-lists skip unentitled tenants

## Readiness payload

`api.app.demo.readiness.demo_readiness(db)` returns checklist flags (`ready_for_paid_demo`, `ready_for_slack_jobs`, etc.). The hardening smoke flips inactive → active and asserts deny/allow.

## Second org (optional, Sprint 22.4)

Platform owner can create another organisation from `/admin/tenants` (`POST /admin/tenants`) or via smoke:

```bash
uv run python scripts/second_org_smoke.py
uv run pytest tests/demo/test_second_org.py -q
```

Smoke stands up `second-org` / `admin-second@example.com` (password `second123`) if missing, lists both tenants, and proves Qdrant search does not leak knowledge across `client_id`s (in-memory fallback when Compose Qdrant is down).

Full spoken demo path (pay → Slack Q&A → …): **`docs/demo-script.md`**. Operator runbooks: **`docs/operator.md`**.
