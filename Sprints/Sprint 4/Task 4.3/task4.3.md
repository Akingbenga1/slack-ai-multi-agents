# Task 4.3 — OAuth install → Postgres

## Steps

- [x] `GET /slack/install?tenant_id=` → Slack authorize redirect
- [x] `GET /slack/oauth/callback` → `oauth.v2.access`, upsert `slack_installs`
- [x] Encrypt bot token at rest; map `team_id` → `client_id`
- [x] `GET /slack/installs/{team_id}` lookup (no token)

## Acceptance criteria

- [x] Install store persists bot token per `team_id` mapped to tenant
- [x] Lookup returns mapping without exposing token
