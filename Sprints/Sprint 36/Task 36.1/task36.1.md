# Task 36.1 — `IdentityProvider` behind token issue

## Steps

- [x] Define `IdentityProvider` Strategy: verify → `AuthPrincipal` (sub, email, role, tenant)
- [x] Implement `CredentialsIdentityProvider` Adapter (password table / `resolve_login_principal`)
- [x] Wire `POST /auth/token` through the Strategy (no direct password verify in the route)
- [x] Keep JWT mint (`create_access_token`) and `AuthPrincipal` as product contracts — not vendor-specific
- [x] Credentials adapter remains the demo path (factory/env in 36.2)
- [x] Light smoke: credentials verify success / failure

## Acceptance criteria

- [x] Strategy used by `POST /auth/token`: verify → `AuthPrincipal`
- [x] Credentials adapter remains the default for demo
- [x] Signup / invite registration stays ordinary product code (not this Strategy)
