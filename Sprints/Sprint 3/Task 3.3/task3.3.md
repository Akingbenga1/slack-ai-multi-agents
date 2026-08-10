# Task 3.3 — Next.js route groups

## Steps

- [x] Add `/admin` and `/app` placeholder dashboards
- [x] Middleware auth guards by role
- [x] Keep `/login`; role-based redirect after sign-in

## Acceptance criteria

- [x] `/admin/*` requires `platform_owner`
- [x] `/app/*` requires `org_admin` (platform redirected to `/admin`)
- [x] Placeholder empty-state pages only
