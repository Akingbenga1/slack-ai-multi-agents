# Task 3.3 journal

## Status

`completed`

## Summary

Added `/admin` and `/app` placeholder shells with `web/middleware.ts` role guards. Login redirects owner → `/admin`, admin → `/app`. Build includes middleware.

## Acceptance criteria checklist

- [x] Admin guard — done
- [x] App guard — done
- [x] Placeholders — done

## Decision log

- Platform owners hitting `/app` redirect to `/admin` to keep shells separate.

## Needs human

None.

## Files changed

- `web/middleware.ts`
- `web/app/admin/*`, `web/app/app/*`
- `web/app/login/page.tsx`, `web/app/page.tsx`

## Resume notes

Task 3.4 membership wiring.

## Open questions

None.
