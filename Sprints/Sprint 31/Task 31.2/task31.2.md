# Task 31.2 — Next.js signup + session

## Steps

- [x] `/signup` (or equivalent) beside `/login`; no pre-provisioned demo credentials required
- [x] Issue JWT/session after signup so the org rep lands in `/app` (`OR-01`, J1 step 1)
- [x] Keep `/login` as sign-in only; do not overload it
- [x] Link home + login → signup

## Acceptance criteria

- [x] Public `/signup` form (org name, email, password; optional slug)
- [x] After success, NextAuth session is org_admin and navigates to `/app`
- [x] `/login` remains credentials sign-in only
- [x] Demo seed credentials are not required for this path
