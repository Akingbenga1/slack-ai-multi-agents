# Task 22.4 journal

## Status

`completed`

## Summary

Added admin create-organisation path and a second-org smoke that proves fail-closed Qdrant isolation between the demo tenant and a newly provisioned org.

## Acceptance criteria checklist

- [x] Create via portal (API + UI)
- [x] No knowledge leak (smoke + pytest)

## Decision log

- Provision creates tenant, org admin, membership, default agent config, billing row; optional `activate_plan` for laptop demo without Stripe.
- Isolation helper prefers live Qdrant, falls back to in-memory so smoke works without Compose.

## Needs human

Live Slack install for the second workspace (same Slack app / tunnel rollup as before).

## Files changed

- `api/app/admin/provision.py`, `api/app/admin/routes.py`, `api/app/demo/isolation.py`
- `web/components/TenantListPanel.tsx`
- `scripts/second_org_smoke.py`, `tests/demo/test_second_org.py`, `tests/admin/test_admin_api.py`
- `docs/admin-portal.md`, `docs/demo-readiness.md`, `docs/demo-script.md`, `README.md`

## Resume notes

Next: **Task 22.5 — Security hygiene**.
