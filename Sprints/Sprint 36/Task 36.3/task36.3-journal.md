# Task 36.3 journal

## Status

`completed`

## Summary

Locked token-issue behind `IdentityProvider`: routes do not import password-table helpers; isolation + factory tests green; login/role/cross-tenant regression green. Marked `review.md` identity gap Implemented. Sprint 36 exit met.

## Acceptance criteria checklist

- [x] Existing login, role guards, and tenant scoping stay green
- [x] Cross-tenant tokens still rejected
- [x] Sprint 36 exit: adding Google/Microsoft/SAML later is a new adapter, not a rewrite of session/JWT issuance

## Decision log

- **Isolation scan:** `auth/routes.py` must not name `resolve_login_principal` / `verify_password` / `hash_password` — credentials adapter owns those.
- Membership role tests still call `resolve_login_principal` directly (domain helper); product token path goes through IdP.

## Needs human

None new. Optional live: copy `IDENTITY_PROVIDER=credentials` into `web/.env.local` if not already using root `.env`.

## Files changed

- `tests/auth/test_identity_isolation.py` (new)
- `Project-Documents/review.md`
- Docs touches from 36.2 (`docs/portal.md`, `README.md`)

## Smoke test results

- `uv run pytest tests/auth/ tests/admin/test_admin_api.py -q` → **31 passed**
- `uv run pytest tests/agent/test_config_api.py::test_config_cross_tenant_denied tests/auth/test_identity_provider.py tests/auth/test_identity_isolation.py tests/auth/test_membership_roles.py -q` → **13 passed**

## Resume notes

**Sprint 36 complete.** Next Ralph batch: **Continue Sprint 37 from Task 37.1** — `BlobStore` + local adapter.

## Open questions

None.
