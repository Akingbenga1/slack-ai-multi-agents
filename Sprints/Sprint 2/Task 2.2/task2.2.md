# Task 2.2 — Core schema migrations

## Steps

- [x] Add SQLAlchemy models for core tables
- [x] Configure Alembic (`alembic.ini` + `env.py`)
- [x] Generate initial migration
- [x] Apply migration against local Postgres
- [x] Document migrate command in README

## Acceptance criteria

- [x] Tables exist: tenants, users, memberships, roles, agent_configs, slack_installs, sync_watermarks, jobs, usage_events, billing_customers
- [x] `alembic upgrade head` succeeds against Compose Postgres
