# Task 31.3 — Invite path (aligned with `/invite`)

## Steps

- [x] Tokenised invite for additional org admins without platform-owner action
- [x] Persist invites in a new table (`invites`: token, tenant_id, email/role, expires_at, used_at)
- [x] Documented token / magic-link URL using existing `WEB_APP_URL` / `JWT_SECRET` / `NEXTAUTH_*`
- [x] Out of scope: SMTP / mail-provider env
- [x] Invited user joins the existing tenant; cannot create a second org from the invite
- [x] Light smoke: create → preview → accept; used/expired/duplicate email rejected

## Acceptance criteria

- [x] Org admin can create an invite and copy `{WEB_APP_URL}/invite?token=…`
- [x] Accept creates user + membership on the **same** tenant (no new tenant row)
- [x] Existing user / second-org from invite is rejected
- [x] `/invite` is no longer a docs-only stub
