# Task 36.1 journal

## Status

`completed`

## Summary

Introduced `IdentityProvider` Strategy and `CredentialsIdentityProvider` Adapter. `POST /auth/token` verifies via the Strategy then mints JWT with unchanged `AuthPrincipal` / `create_access_token`. Signup/invite remain ordinary product code.

## Acceptance criteria checklist

- [x] Strategy used by `POST /auth/token`: verify → `AuthPrincipal`
- [x] Credentials adapter remains the default for demo
- [x] Signup / invite registration stays ordinary product code (not this Strategy)

## Decision log

- **Patterns:** Strategy (`IdentityProvider`) + Adapter (`CredentialsIdentityProvider`). Factory deferred to Task 36.2 but landed in the same batch in `provider.py` (same shape as payment/embedding).
- **`AuthPrincipal`** stays the product contract; adapter maps from `LoginPrincipal` (`resolve_login_principal` remains membership/password-table helper owned by the credentials adapter).
- JWT issuance stays outside the IdP — verify then mint.

## Needs human

None new.

## Files changed

- `api/app/auth/provider.py` (new)
- `api/app/auth/credentials_adapter.py` (new)
- `api/app/auth/routes.py`, `__init__.py`
- `tests/auth/test_identity_provider.py` (partial — verify smoke)

## Resume notes

Done. Continue Task 36.2 — factory + `IDENTITY_PROVIDER` + NextAuth.

## Open questions

None.
