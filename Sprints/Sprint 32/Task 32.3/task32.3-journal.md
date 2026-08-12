# Task 32.3 journal

## Status

completed

## Summary

Documented the three independent billing/access concepts for operators. Added `ALLOW_PLAN_WAIVERS` with smart default (`development` → allowed; `staging`/`production` → denied unless explicitly `true`). Activating a waiver returns 403 when disabled; deactivating (restore Stripe) still permitted.

## Acceptance criteria checklist

- [x] Semantics documented
- [x] Webhook honour `plan_source=admin` (32.1)
- [x] `ALLOW_PLAN_WAIVERS` in settings + `.env.example`
- [x] No Stripe env renames

## Decision log

- `allow_plan_waivers: bool | None = None` + `plan_waivers_permitted()` property for env-default-by-`app_env`.
- Guardrail applies only to `plan_status=active` (new waivers), not deactivate.

## Needs human

(none)

## Files changed

- `api/app/settings.py`
- `api/app/admin/actions.py`
- `api/app/admin/routes.py`
- `docs/admin-portal.md`
- `docs/billing.md`
- `.env.example`

## Resume notes

Continue **Task 32.4** — regression tests.

## Open questions

(none)

## Smoke test results

`uv run pytest tests/admin/test_plan_override_sprint32.py::test_allow_plan_waivers_guardrail tests/admin/test_plan_override_sprint32.py::test_plan_waivers_default_by_app_env -q`
