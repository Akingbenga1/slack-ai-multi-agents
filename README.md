# Client Slack AI Agents

Multi-tenant Slack AI agent platform: one shared stack, strong per-client isolation (knowledge, prompts, Slack install, budgets, billing).

**Demo posture:** laptop-as-VPS. Team members use Slack; org reps and the platform owner use Next.js.

Planning docs: `Project-Documents/` (especially `jira-task.md`). Sprint work: `Sprints/`.
**Operator bring-up:** `docs/operator.md`. **Demo script:** `docs/demo-script.md`.

## Pieces

| Path | Role |
| ---- | ---- |
| `api/` | FastAPI gateway — Slack HTTP Events, tenant APIs, Stripe webhooks, JWT auth |
| `web/` | Next.js App Router — `/admin` (platform owner), `/app` (org portal), auth |
| `worker/` | Celery Beat + workers — sync, reports, briefs, ingest jobs |
| `mcp_server/` | Bundled MCP process — tools enforce `client_id` |
| `tests/` | Shared / integration tests |
| `data/` | Local runtime data (uploads, dumps); **gitignored** |

## Setup (toolchains)

```bash
# Python (api / worker / mcp_server) — requires uv + Python 3.11+
uv sync

# Next.js
cd web && npm install
```

## Local services (Docker Compose)

Postgres, Redis, Qdrant, and TEI (embeddings) run via Compose. App processes (`uvicorn`, `next dev`, Celery) run on the host against those URLs.

```bash
cp .env.example .env
docker compose up -d
```

## App processes (laptop-VPS host)

```bash
# API — http://localhost:8000/health
uv run uvicorn api.app.main:app --reload --port 8000

# Web — http://localhost:3000 (shows "OK"; /login for Auth.js demo)
cd web && npm run dev

# Celery worker (Redis broker) — consume priority queues
# Windows laptop-VPS: --pool=solo (prefork unsupported)
uv run celery -A worker.celery_app worker --loglevel=INFO -Q high,default,low --pool=solo

# Celery Beat — periodic schedules (separate terminal)
uv run celery -A worker.celery_app beat --loglevel=INFO
```

Queues, Beat heartbeat, and job metadata: `docs/celery.md`.
Qdrant + TEI (collection, fail-closed `client_id`, embed client): `docs/qdrant-tei.md`.
Knowledge retrieval (`search_knowledge` top-k + citations): `docs/retrieval.md`.
Slack history dump parsers + ingest CLI (ZIP / JSON / NDJSON / CSV / XLSX → TEI → Qdrant): `docs/slack-history-ingest.md`.
Document parsers + multipart uploads + Celery ingest: `docs/document-ingest.md`, `docs/uploads.md`.
Demo logins (Task 3.1): `owner@example.com` / `owner123` (platform_owner → `/admin`), `admin@example.com` / `admin123` (org_admin → `/app`).
Platform admin portal (Sprint 21): `docs/admin-portal.md`.
Demo readiness (Sprint 22.1): `docs/demo-readiness.md`.
Operator runbook (Sprint 22.2): `docs/operator.md`.
Demo script (Sprint 22.3): `docs/demo-script.md`.
Security hygiene (Sprint 22.5): `docs/security.md`.
Org portal (Sprint 19–20): `docs/portal.md`.

Tunnel plan for Slack/Stripe later: `docs/tunnel-plan.md`.
Stripe billing (customers, Checkout, Customer Portal): `docs/billing.md`.
Governance (per-tenant RPM, budgets, usage events): `docs/governance.md`.

```bash
# Sprint 6 isolation smoke (Compose Qdrant + TEI must be up)
uv run python scripts/qdrant_isolation_smoke.py

# Sprint 7 history ingest (sample dump → searchable for one tenant)
uv run python scripts/ingest_slack_history.py \
  --client-id 11111111-1111-1111-1111-111111111111 \
  --format json --path data/sample_history.json \
  --query "onboarding checklist"

# Sprint 10 retrieval (tenant-safe search_knowledge + corpus smoke)
uv run pytest tests/retrieval -q
uv run python scripts/search_knowledge_smoke.py

# Sprint 22.1 first-org hardening (seed + entitlement deny/allow)
# Optional: DEMO_ACTIVATE_PLAN=true in .env before seed
uv run python scripts/seed_demo.py
uv run python scripts/first_org_hardening_smoke.py
uv run pytest tests/demo/test_first_org_hardening.py -q

# Sprint 22.4 second org + no knowledge leak
uv run python scripts/second_org_smoke.py
uv run pytest tests/demo/test_second_org.py -q
```

## Database migrations

```bash
uv run alembic upgrade head
uv run python scripts/seed_demo.py
```

Postgres is published on **host port 5433** (`localhost:5433`) to avoid clashing with any local Postgres on 5432.

API auth: `POST /auth/token` → Bearer JWT; `GET /auth/me`, `/auth/tenant-ping`, `/auth/membership`.
Jobs stub: `POST /jobs/heartbeat` (Bearer required) enqueues a tenant heartbeat — see `docs/celery.md`.
Jobs stub: `POST /jobs/recurring-report` force-posts a digest (schedule channel or body `channel_id`) — see `docs/celery.md`.
Live Slack sync: `POST /jobs/slack-history-sync` (on-demand); `GET`/`PATCH /jobs/slack-history-sync/schedule` (Beat enable/disable); `GET /jobs/slack-history-sync/status` (last success/failure); hourly Beat dispatcher — see `docs/celery.md`.
Slack file actions (Sprint 23): attach → analyse → PDF upload → rename — `docs/slack-file-actions.md`.
Recurring report schedule: `GET`/`PATCH /jobs/recurring-report/schedule` — see `docs/celery.md`.
Knowledge upload: `POST /uploads` (Bearer + multipart `file` + `file_role`) — see `docs/uploads.md`. Ingest status: `GET /uploads/jobs`. Org portal: `/app/agent`, `/app/knowledge`, `/app/billing`, `/app/usage`, `/app/slack` (`docs/portal.md`); sign in as `admin@example.com` after API + seed.

Slack (Sprint 4): see `docs/slack-app-setup.md` — Events `{PUBLIC_BASE_URL}/slack/events`, install `/slack/install?tenant_id=…`.
Live Slack Web API client + history sync task (`worker.slack_history_sync`): `docs/slack-web-api.md`, `docs/celery.md`.

Agent dry-run (Sprint 13, offline — no Slack post): `POST /agent/dry-run` (Bearer) or `uv run python scripts/agent_dry_run.py --client-id … --question …` — see `docs/agent.md`.

Bundled MCP (Sprint 15–17, stdio): `uv run python -m mcp_server` — tools `search_knowledge`, `draft_meeting_brief`, `draft_meeting_agenda`, `draft_meeting_notes`, `draft_report` (tenant `client_id` required). Agent **tools** node calls MCP as a client (default). Recurring digests: `run_report` / `docs/agent.md`. See `docs/mcp.md`.

## Locked stack (summary)

Anthropic + LangGraph + Qdrant + TEI + PostgreSQL + Redis/Celery + Slack HTTP Events + Stripe + FastAPI + Next.js.

See `Project-Documents/architecture-description.md` and `Project-Documents/technology-stack-document.md`.
