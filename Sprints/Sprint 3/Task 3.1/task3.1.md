# Task 3.1 — Auth.js (NextAuth) setup

## Steps

- [x] Install `next-auth` in `web/`
- [x] Credentials provider with demo `platform_owner` and `org_admin` users
- [x] Session carries role (+ tenant id for org_admin)
- [x] `/login` page + auth route handler
- [x] Document env vars (`NEXTAUTH_SECRET`, `NEXTAUTH_URL`)

## Acceptance criteria

- [x] Can sign in as platform_owner and org_admin (demo credentials)
- [x] Session exposes role for later route guards
