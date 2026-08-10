# Operator runbook

Single bring-up path for the **laptop-as-VPS** demo. Deep dives stay in topic docs; this page is the order of operations.

## 0. Prerequisites

- Docker Desktop (Compose: Postgres, Redis, Qdrant, TEI)
- Python 3.11+ with `uv`, Node.js for `web/`
- Copy env: `cp .env.example .env` (and `web/.env.local` for Next.js — see below)

## 1. Compose services

```bash
docker compose up -d
docker compose ps   # postgres, redis, qdrant, tei healthy
```

| Service | Default URL / note |
| ------- | ------------------ |
| Postgres | `localhost:5433` (`DATABASE_URL`) |
| Redis | `localhost:6379` (`REDIS_URL`) |
| Qdrant | `http://localhost:6333` — `docs/qdrant-tei.md` |
| TEI | `http://localhost:8080` — embedding model must match `EMBEDDING_DIM` |

## 2. Database + demo seed

```bash
uv sync
uv run alembic upgrade head
uv run python scripts/seed_demo.py
```

| Login | Role | Portal |
| ----- | ---- | ------ |
| `owner@example.com` / `owner123` | platform_owner | `/admin` |
| `admin@example.com` / `admin123` | org_admin | `/app` |

Demo tenant id: `11111111-1111-1111-1111-111111111111`. Optional local plan without Stripe: `DEMO_ACTIVATE_PLAN=true` — see `docs/demo-readiness.md`.

## 3. App processes (host)

```bash
# API
uv run uvicorn api.app.main:app --reload --port 8000

# Web
cd web && npm install && npm run dev   # :3000

# Celery worker (Windows: --pool=solo)
uv run celery -A worker.celery_app worker --loglevel=INFO -Q high,default,low --pool=solo

# Celery Beat (sync + reports dispatchers)
uv run celery -A worker.celery_app beat --loglevel=INFO
```

Queues / schedules: `docs/celery.md`. Health: `GET http://localhost:8000/health`.

### Next.js env (`web/.env.local`)

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=dev-nextauth-secret-change-me
```

Auth shells: platform `/admin`, org `/app` (JWT mint via API when seeded).

## 4. Tunnel (public HTTPS)

Required for Slack Events, OAuth callback, and Stripe webhooks.

- Plan: `docs/tunnel-plan.md`
- Set `PUBLIC_BASE_URL=https://…` to the tunnel host pointing at `:8000`

## 5. Stripe

| Env | Purpose |
| --- | ------- |
| `STRIPE_SECRET_KEY` | API |
| `STRIPE_PRICE_ID` | Checkout line item |
| `STRIPE_WEBHOOK_SECRET` | `POST /billing/webhooks/stripe` |

Details: `docs/billing.md`. Webhook URL: `{PUBLIC_BASE_URL}/billing/webhooks/stripe`. Without keys, use `DEMO_ACTIVATE_PLAN=true` for local entitlement smoke.

## 6. Slack OAuth + Events

| Env | Purpose |
| --- | ------- |
| `SLACK_CLIENT_ID` / `SLACK_CLIENT_SECRET` | Install |
| `SLACK_SIGNING_SECRET` | Events verify |

Checklist: `docs/slack-app-setup.md`. Live Web API sync: `docs/slack-web-api.md`.

- Events: `{PUBLIC_BASE_URL}/slack/events`
- Install: `{PUBLIC_BASE_URL}/slack/install?tenant_id=<DEMO_TENANT_ID>`
- Optional seed fixture: `DEMO_SLACK_TEAM_ID` + `DEMO_SLACK_BOT_TOKEN`

## 7. TEI / Qdrant / retrieval

- Collection + fail-closed `client_id`: `docs/qdrant-tei.md`
- `search_knowledge`: `docs/retrieval.md`
- Isolation smoke: `uv run python scripts/qdrant_isolation_smoke.py`
- Second org + isolation: `uv run python scripts/second_org_smoke.py` (`docs/demo-readiness.md`)

## 8. Celery jobs operators care about

| Job | Trigger |
| --- | ------- |
| Live Slack history sync | `POST /jobs/slack-history-sync` or hourly Beat |
| Recurring report | `POST /jobs/recurring-report` or daily/weekly Beat |
| Upload ingest | `POST /uploads` |

Requires **active plan** entitlements (`sync` / `ingest` / `agent`) — unpaid paths return 403. Status UIs: org `/app/knowledge`, `/app/slack`.

## 9. Bundled MCP

```bash
uv run python -m mcp_server
```

Tools require `client_id`. Agent default: `AGENT_RETRIEVE_BACKEND=mcp`. Docs: `docs/mcp.md`. Optional Anthropic: `ANTHROPIC_API_KEY` (`docs/agent.md`).

## 10. Portals quick map

| Area | Path | Doc |
| ---- | ---- | --- |
| Org home / banners | `/app` | `docs/portal.md` |
| Agent / knowledge / billing / usage / Slack | `/app/*` | `docs/portal.md` |
| Admin tenants / health | `/admin/*` | `docs/admin-portal.md` |

## 11. First-org hardening check

```bash
uv run python scripts/first_org_hardening_smoke.py
uv run pytest tests/demo/test_first_org_hardening.py -q
```

Spoken demo path: `docs/demo-script.md`.

## Topic index

| Topic | Doc |
| ----- | --- |
| Tunnel | `docs/tunnel-plan.md` |
| Slack app | `docs/slack-app-setup.md` |
| Slack Web API | `docs/slack-web-api.md` |
| Billing | `docs/billing.md` |
| Governance | `docs/governance.md` |
| Celery | `docs/celery.md` |
| Qdrant / TEI | `docs/qdrant-tei.md` |
| Retrieval | `docs/retrieval.md` |
| Agent | `docs/agent.md` |
| MCP | `docs/mcp.md` |
| Uploads / ingest | `docs/uploads.md`, `docs/document-ingest.md` |
| Onboarding stub | `docs/onboarding.md` |
| Demo readiness | `docs/demo-readiness.md` |
| Demo script | `docs/demo-script.md` |
| Security hygiene | `docs/security.md` |
| Org portal | `docs/portal.md` |
| Admin portal | `docs/admin-portal.md` |
