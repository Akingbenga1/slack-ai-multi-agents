# Task 30.1 journal

## Status

completed

## Summary

Unified fail-closed `require_client_id` / `ClientIdRequired` in `api/app/tenant.py` and HTTP `resolve_tenant_for_principal` in `api/app/auth/tenant_resolve.py`. Migrated route modules and domain wrappers (Qdrant, Slack files, workflows, agent guardrails) to wrap messages only. PDF stem sanitize now reuses uploads `sanitize_filename`.

## Acceptance criteria checklist

- [x] One shared HTTP tenant resolve used by the listed route modules
- [x] One shared fail-closed `require_client_id` spine; domain modules wrap messages only
- [x] Uploads + PDF share filename sanitize logic
- [x] No intentional behavior change for org vs platform_owner tenant rules

## Decision log

- **Consistency, not a GoF pattern** (`review.md` §5.8 / P6): shared helpers only — no Strategy/Factory for tenant id.
- Domain wrappers keep existing exception types (`TenantFilterRequired`, `TenantContextRequired`, Slack/workflow `ValueError`) so tests and call sites stay stable.
- PDF sanitize applies `sanitize_filename` to the stem (not the full name) to preserve prior stem-first behavior.

## Needs human

(none new)

## Files changed

- `api/app/tenant.py`
- `api/app/auth/tenant_resolve.py` (new)
- `api/app/qdrant/tenant.py`
- `api/app/agent/guardrails.py`
- `api/app/slack/files/refs.py`
- `api/app/slack/pdf_export.py`
- `api/app/workflows/library.py`
- `api/app/jobs/routes.py`
- `api/app/uploads/routes.py`
- `api/app/billing/routes.py`
- `api/app/governance/routes.py`
- `api/app/slack/routes.py`
- `api/app/workflows/routes.py`
- `api/app/agent/routes.py`

## Smoke test results

- `test_require_tenant_client_id_fail_closed`, `test_require_client_id_fail_closed` (Slack + workflows): 3 passed
- Manual import smoke for PDF stem + typed errors

## Resume notes

Continue with Task 30.2 — web `apiClient` + migrate heaviest panels.

## Open questions

(none)
