# Task 36.2 journal

## Status

`completed`

## Summary

Added `IDENTITY_PROVIDER=credentials` (Settings + `.env.example`), API factory `get_identity_provider`, and NextAuth factory `getAuthProviders()`. Future OIDC/SAML/Google/Microsoft raise documented “not implemented” — no second-IdP env keys or `user_identities` table. Registration unchanged.

## Acceptance criteria checklist

- [x] `IDENTITY_PROVIDER=credentials` is the demo default; factory selects adapter
- [x] No OIDC/SAML env keys or second IdP implementation this sprint
- [x] Existing auth keys unchanged; registration unchanged

## Decision log

- **Patterns:** Factory Method on API (`get_identity_provider`) and web (`getAuthProviders`) so a second IdP is a new adapter + provider entry, not a JWT/session rewrite.
- Web credentials path still calls `POST /auth/token` (API owns verify); NextAuth only selects which provider module to wire.
- Shared `IDENTITY_PROVIDER` env for API + Next.js (copy into `web/.env.local`).

## Needs human

None new.

## Files changed

- `api/app/settings.py` (`identity_provider`)
- `api/app/auth/provider.py` (factory)
- `web/lib/auth.ts` (`getAuthProviders`)
- `.env.example`, `docs/portal.md`, `README.md`
- `tests/auth/test_identity_provider.py` (factory cases)

## Resume notes

Done. Continue Task 36.3 — isolation + regression.

## Open questions

None.
