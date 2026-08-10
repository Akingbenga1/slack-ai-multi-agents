# Task 3.2 — FastAPI JWT validation

## Steps

- [x] Issue JWT from FastAPI (`/auth/token`) with role + tenant claims
- [x] Auth dependency: validate Bearer JWT
- [x] Reject cross-tenant access for org-scoped routes
- [x] Light smoke: valid token ok; wrong tenant → 403

## Acceptance criteria

- [x] API can issue and accept JWTs signed with `JWT_SECRET`
- [x] Cross-tenant access rejected for non-platform roles
