# Task 22.1 journal

## Status

`completed`

## Summary

Hardened first-org demo seed (optional plan activation + Slack/report fixtures), closed unpaid sync/ingest/report enqueue holes, filtered Beat due-lists by entitlements, and added readiness helper + smoke/tests.

## Acceptance criteria checklist

- [x] Demo-ready seed without live Stripe (`DEMO_ACTIVATE_PLAN`)
- [x] Unpaid cannot enqueue sync / ingest / report
- [x] Hardening smoke / pytest with fixtures

## Decision log

- `require_entitlement` + `require_budget(..., require_active_plan=True)` on product job paths; heartbeat stays budget-only.
- Beat sync requires `sync`; Beat reports require `agent`.
- Smoke CLIs/docs prefer `DEMO_TENANT_ID` so knowledge matches the portal org.

## Needs human

Inherited: live Stripe / Slack OAuth / tunnel / Anthropic verify (unchanged). Optional: set `DEMO_ACTIVATE_PLAN=true` (and Slack/report env) for laptop demo without Checkout.

## Files changed

- `api/app/settings.py`, `membership.py`, `billing/plans.py`, `billing/__init__.py`
- `api/app/jobs/routes.py`, `uploads/routes.py`, `slack/schedule.py`, `reports/schedule.py`, `slack/store.py`
- `api/app/demo/*`, `scripts/first_org_hardening_smoke.py`, `scripts/agent_dry_run.py`
- `tests/demo/*`, schedule/upload/report API test mocks
- `docs/demo-readiness.md`, `docs/billing.md`, `docs/governance.md`, `.env.example`, `README.md`

## Resume notes

Next in batch: **Task 22.2 — Operator documentation**.

## Commercial mapping

Platform owner / org demo path: one org pay → operate without unpaid side doors.
