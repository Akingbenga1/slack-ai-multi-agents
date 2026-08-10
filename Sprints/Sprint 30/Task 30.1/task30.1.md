# Task 30.1 — Shared tenant resolve + `require_client_id`

## Steps

- [x] Add fail-closed `require_client_id` (+ typed `ClientIdRequired`) in `api/app/tenant.py`
- [x] Keep domain wrappers (Qdrant / Slack files / workflows / agent) that only customize messages / exception types
- [x] Add `resolve_tenant_for_principal(principal, requested_id)` for HTTP modules
- [x] Migrate jobs / uploads / billing / governance / slack / workflows / agent routes off local copies
- [x] Reuse `sanitize_filename` in PDF export (`sanitize_pdf_stem`)
- [x] Light smoke: existing fail-closed tests still pass

## Acceptance criteria

- [x] One shared HTTP tenant resolve used by the listed route modules
- [x] One shared fail-closed `require_client_id` spine; domain modules wrap messages only
- [x] Uploads + PDF share filename sanitize logic
- [x] No intentional behavior change for org vs platform_owner tenant rules
