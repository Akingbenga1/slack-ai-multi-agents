# Task 31.4 journal

## Status

completed

## Summary

Regression pass for Sprint 31: owner `POST /admin/tenants` still provisions a distinct org after public signup; demo seed + `DEMO_ACTIVATE_PLAN` still activates the demo tenant; self-signup ignores that flag and needs no new env keys. Documented that Sprint 18 Slack `start_onboarding` is unchanged and is **not** tenant signup. Marked the `review.md` self-service org-onboarding gap as implemented.

## Acceptance criteria checklist

- [x] `POST /admin/tenants` still provisions a distinct org (owner JWT) after a public signup
- [x] `DEMO_ACTIVATE_PLAN` still activates the **demo seed** tenant; self-signup plan stays inactive
- [x] `.env.example` / `Settings` gain no signup-specific keys
- [x] Docs state Slack `start_onboarding` stub ≠ `/signup` tenant registration

## Decision log

- No product-code change — signup already reused `create_organisation` with `activate_plan=False` and `audit_source=self_signup`. This task is tests + docs.
- SQLite cannot ORM-load well-known demo UUIDs (`1111…` / `2222…` stored as floats); regression asserts use column queries (`Tenant.slug` + `BillingCustomer.plan_status`) and HTTP status.
- No Strategy/Factory (Sprint 31 product gap).

## Needs human

Optional: `alembic upgrade head` then live `/signup` + `/invite` against API + Next.js (unchanged from 31.3).

## Files changed

- `tests/auth/test_provision_regression.py` — owner create after signup; demo seed vs signup plan; no signup env keys; onboarding stub unchanged
- `docs/onboarding.md`, `docs/portal.md`, `docs/admin-portal.md`, `docs/demo-readiness.md`, `docs/mcp.md`, `docs/agent.md`, `docs/demo-script.md`, `docs/operator.md`, `README.md` — stub ≠ signup; owner path + `DEMO_ACTIVATE_PLAN` still work
- `.env.example` — comment that signup reuses JWT / `WEB_APP_URL` / NextAuth
- `Project-Documents/review.md` — self-service org onboarding gap marked implemented

## Resume notes

**Sprint 31 complete.** Next Ralph batch: **Sprint 32 / Task 32.1** — admin plan override API (`PATCH /admin/tenants/{id}/plan`).

## Open questions

(none)

## Smoke test results

`uv run pytest tests/auth/test_provision_regression.py -q` — 4 passed.

Related: `tests/auth/test_signup.py tests/auth/test_invites.py tests/admin/test_admin_api.py tests/agent/test_onboarding.py tests/demo/test_first_org_hardening.py` — 24 passed.
