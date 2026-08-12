# Task 36.2 — NextAuth / factory

## Steps

- [x] Add `IDENTITY_PROVIDER=credentials` (demo default) to Settings + `.env.example`
- [x] Factory `get_identity_provider` selects credentials vs future OIDC/SAML (documented stubs only)
- [x] NextAuth providers built via factory — credentials only this sprint; no Google/Microsoft/SAML
- [x] Keep `JWT_SECRET`, `NEXTAUTH_URL`, `NEXTAUTH_SECRET`; no `user_identities` table
- [x] Signup (Sprint 31) still creates the user row — this sprint does not replace registration
- [x] Docs: identity provider selector noted near auth / portal

## Acceptance criteria

- [x] `IDENTITY_PROVIDER=credentials` is the demo default; factory selects adapter
- [x] No OIDC/SAML env keys or second IdP implementation this sprint
- [x] Existing auth keys unchanged; registration unchanged
