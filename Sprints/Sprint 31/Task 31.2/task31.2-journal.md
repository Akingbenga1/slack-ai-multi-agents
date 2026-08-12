# Task 31.2 journal

## Status

completed

## Summary

Added Next.js `/signup` beside `/login`. The form calls `POST /auth/signup`, then `signIn("credentials")` so the org rep lands in `/app` with a session. Login stays sign-in only; demo credentials are not prefilled on signup.

## Acceptance criteria checklist

- [x] Public `/signup` form (org name, email, password; optional slug)
- [x] After success, NextAuth session is org_admin and navigates to `/app`
- [x] `/login` remains credentials sign-in only
- [x] Demo seed credentials are not required for this path

## Decision log

- After API signup, reuse existing NextAuth credentials `authorize` (token + `/auth/me`) rather than stuffing the signup JWT into the session by hand.
- No new env keys (`NEXT_PUBLIC_API_BASE_URL` / NextAuth already required).
- No Strategy/Factory.

## Needs human

(none)

## Files changed

- `web/app/signup/page.tsx`
- `web/app/login/page.tsx` — link to `/signup`
- `web/app/page.tsx` — link to `/signup`
- `docs/portal.md` — `/signup` route

## Resume notes

Continue with Task 31.3 — tokenised invite table + `/invite` accept/create.

## Open questions

(none)
