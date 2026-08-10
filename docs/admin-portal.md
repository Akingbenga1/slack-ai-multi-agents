# Platform admin portal (Sprint 21)

Next.js `/admin` for `platform_owner` (`owner@example.com` / `owner123`).

## Routes

| Path | Purpose |
| ---- | ------- |
| `/admin` | Admin home |
| `/admin/tenants` | Tenant list — plan, Slack, last sync (PO-01 / PO-25) |
| `/admin/tenants/[id]` | Tenant detail + suspend / budget override + audit (21.3) |
| `/admin/health` | Compose deep health + job/usage error rates (PO-13) |

## APIs

| Method | Path | Notes |
| ------ | ---- | ----- |
| `GET` | `/admin/tenants` | Owner only — list summaries |
| `POST` | `/admin/tenants` | Create org (slug, name, admin email/password, optional `activate_plan`) — PO-04 |
| `GET` | `/admin/tenants/{id}` | Detail + embedded sync status |
| `GET` | `/admin/health?hours=24` | Deep health + failed jobs / usage |
| `PATCH` | `/admin/tenants/{id}/status` | `{ "status": "active" \| "suspended" }` + audit |
| `PATCH` | `/admin/tenants/{id}/budgets` | Override `tokens_daily` / `tokens_monthly` / `jobs_daily` + audit |
| `GET` | `/admin/audit-logs?tenant_id=&limit=` | Recent support actions |

`POST /admin/tenants` creates tenant + org admin membership + billing row + default agent config, audited as `tenant.created`. If `admin_password` is omitted, a password is generated and returned once.

Suspended tenants fail `plan_is_active` and Slack agent replies with a clear suspended message.

## Smoke

```bash
uv run alembic upgrade head
uv run python scripts/seed_demo.py
uv run pytest tests/admin -q

# Second org + knowledge isolation (Sprint 22.4)
uv run python scripts/second_org_smoke.py
uv run pytest tests/demo/test_second_org.py -q

# Web: sign in as owner@example.com → /admin/tenants (create form), /admin/health
```
