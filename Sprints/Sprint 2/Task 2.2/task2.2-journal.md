# Task 2.2 journal

## Status

`completed`

## Summary

Added SQLAlchemy models for all core tables, Alembic env wired to Settings, generated `648a45c928b1_initial_core_schema`, applied with `alembic upgrade head`. Verified table list in Postgres.

## Acceptance criteria checklist

- [x] All listed tables exist — done
- [x] `alembic upgrade head` succeeds — done

## Decision log

- SQLAlchemy 2 + Alembic for migrations.
- JSONB for flexible agent/slack/job payloads.
- Roles as a lookup table; memberships join tenant↔user↔role.

## Needs human

None.

## Files changed

- `api/app/db/models.py`, `session.py`, `__init__.py`
- `alembic/`, `alembic.ini`
- `pyproject.toml` / lock (sqlalchemy, alembic)
- `README.md` (migrate + port 5433 note)

## Schema / migration notes

- Revision: `648a45c928b1` — `initial_core_schema`
- Tables: `tenants`, `users`, `roles`, `memberships`, `agent_configs`, `slack_installs`, `sync_watermarks`, `jobs`, `usage_events`, `billing_customers`

## Resume notes

Next batch: Task 2.3 — Tenant context helpers.

## Open questions

None.

## Smoke test results

- `alembic upgrade head` — ok
- Inspect tables — all expected names present
