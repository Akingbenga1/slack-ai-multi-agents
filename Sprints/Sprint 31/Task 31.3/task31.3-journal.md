# Task 31.3 journal

## Status

completed

## Summary

Added an `invites` table and tokenised org-admin invites. Org admins create a copyable `{WEB_APP_URL}/invite?token=…` link (HMAC with `JWT_SECRET`; no SMTP). Accepting the invite creates a user + membership on the **existing** tenant and issues a session into `/app`. Used, expired, and duplicate-email invites are rejected. `/invite` is a working create/accept UI, not a docs stub.

## Acceptance criteria checklist

- [x] Org admin can create an invite and copy `{WEB_APP_URL}/invite?token=…`
- [x] Accept creates user + membership on the **same** tenant (no new tenant row)
- [x] Existing user / second-org from invite is rejected
- [x] `/invite` is no longer a docs-only stub

## Decision log

- Store `token_hash` = HMAC-SHA256(`JWT_SECRET`, raw token); raw token returned once on create (same posture as generated admin passwords).
- TTL 7 days. Role is `org_admin` only (MVP additional admins).
- Accept never calls `create_organisation` — membership only, so a second org cannot be created from the invite.
- No new env keys; SMTP explicitly out of scope.
- No Strategy/Factory.

## Needs human

(none)

## Files changed

- `api/app/db/models.py` — `Invite`
- `alembic/versions/f6a2c43d0e51_invites.py`
- `api/app/auth/invites.py`
- `api/app/auth/routes.py` — create / list / preview / accept
- `tests/auth/test_invites.py`
- `web/app/invite/page.tsx`
- `web/components/InvitePanel.tsx`
- `docs/portal.md`

## Schema / migration notes

Apply `alembic upgrade head` (`f6a2c43d0e51`) before using invites against Postgres.

## Resume notes

Next Ralph batch: **Task 31.4** — regression vs owner provisioning (admin create still works; demo seed / `DEMO_ACTIVATE_PLAN`; document Slack onboarding stub ≠ tenant signup).

## Open questions

(none)

## Smoke test results

`uv run pytest tests/auth/test_signup.py tests/auth/test_invites.py tests/demo/test_second_org.py tests/auth/test_membership_roles.py -q` — 15 passed.
