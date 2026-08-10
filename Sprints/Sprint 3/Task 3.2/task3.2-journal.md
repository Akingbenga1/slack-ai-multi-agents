# Task 3.2 journal

## Status

`completed`

## Summary

Added FastAPI JWT issue/validate: `POST /auth/token`, `GET /auth/me`, `GET /auth/tenant-ping` with `require_tenant_access` rejecting cross-tenant `X-Client-Id` for org_admin.

## Acceptance criteria checklist

- [x] Issue/accept JWT — done
- [x] Cross-tenant rejected — done (403)

## Decision log

- HS256 with `Settings.jwt_secret`; claims: `sub`, `email`, `role`, `tenant_id`, `all_access`.
- bcrypt pinned to 4.0.1 for passlib compatibility.

## Needs human

None.

## Files changed

- `api/app/auth/tokens.py`, `deps.py`, `routes.py`
- `api/app/main.py` (router + CORS)
- `pyproject.toml` (pyjwt/passlib/bcrypt/email-validator)

## Resume notes

Continue 3.3–3.4 in same batch.

## Open questions

None.

## Smoke test results

- Admin same-tenant ping → 200
- Admin cross-tenant ping → 403 `Cross-tenant access denied`
