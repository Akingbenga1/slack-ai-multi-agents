# Task 3.1 journal

## Status

`completed`

## Summary

Installed NextAuth v4 with Credentials provider and demo users for `platform_owner` and `org_admin`. JWT session carries `role` and `tenantId`. Added `/login` and `/api/auth/[...nextauth]`. `web/.env.local` + root `.env.example` document secrets. Next.js build passes.

## Acceptance criteria checklist

- [x] Demo sign-in for both roles — done (UI + authorize)
- [x] Session exposes role — done (typed session callbacks)

## Decision log

- NextAuth v4 (stable App Router route handler) rather than Auth.js v5 beta.
- Demo credentials hardcoded for MVP; DB-backed auth in later tasks.
- org_admin demo tenantId: `11111111-1111-1111-1111-111111111111`

## Needs human

None (demo secrets only). Real OAuth/email later.

## Files changed

- `web/lib/auth.ts`, `web/types/next-auth.d.ts`
- `web/app/api/auth/[...nextauth]/route.ts`
- `web/app/login/page.tsx`, `web/app/page.tsx`, `web/app/layout.tsx`
- `web/.env.local`, `.env.example`, `README.md`
- `web/package.json` (next-auth)

## Credentials / env vars

- `web/.env.local`: `NEXTAUTH_URL`, `NEXTAUTH_SECRET`, `NEXT_PUBLIC_API_BASE_URL`
- Demo: `owner@example.com` / `owner123`; `admin@example.com` / `admin123`

## Resume notes

Next: Task 3.2 — FastAPI JWT validation.

## Open questions

None.

## Smoke test results

- `npm run build` — success (routes `/`, `/login`, `/api/auth/[...nextauth]`)
