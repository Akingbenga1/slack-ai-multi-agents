# Task 31.1 journal

## Status

completed

## Summary

Added public `POST /auth/signup` that reuses `create_organisation` (same tenant + org admin + membership + billing + default agent config as `POST /admin/tenants`). Self-signup never activates the plan (`DEMO_ACTIVATE_PLAN` is ignored). Duplicate email/slug return 409. JWT is issued so the org rep can enter `/app` without a platform-owner ticket.

## Acceptance criteria checklist

- [x] Public `POST /auth/signup` (no platform-owner JWT) provisions the same rows as admin create
- [x] Duplicate email / slug → 409
- [x] New org is a distinct `tenant_id` from demo / other signups
- [x] No new env keys; no Strategy/Factory

## Decision log

- Reused `create_organisation` rather than a second provisioner. Added `audit_source=self_signup` so admin create vs signup is distinguishable in `audit_logs`.
- Optional `slug`; when omitted, derive from org name and allocate `name-<hex>` on collision.
- Password required (min 8); no generated password (unlike admin create).
- No Strategy/Factory (Sprint 31 product gap).

## Needs human

(none)

## Files changed

- `api/app/admin/provision.py` — `slug_from_name`, `allocate_unique_slug`, `audit_source`
- `api/app/auth/signup.py` — `register_organisation`
- `api/app/auth/routes.py` — `POST /auth/signup`
- `tests/auth/test_signup.py`

## Resume notes

Continue with Task 31.2 — Next.js `/signup` + session into `/app`.

## Open questions

(none)

## Smoke test results

`uv run pytest tests/auth/test_signup.py tests/demo/test_second_org.py -q` — signup tests green; second-org provision still green.
