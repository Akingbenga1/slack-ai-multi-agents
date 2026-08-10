# Task 4.3 journal

## Status

`completed`

## Summary

OAuth install flow stores encrypted bot tokens in `slack_installs` with `team_id` → `tenant_id` (`client_id`). Fernet key derived from `JWT_SECRET`. Demo upsert + lookup smoked locally; live Slack OAuth Needs human.

## Acceptance criteria checklist

- [x] Persist install mapped to tenant — done
- [x] Lookup without token — done

## Decision log

- OAuth `state` = `tenant_id` UUID.
- Bot scopes constant in `routes.py` matches docs checklist.
- Token encryption via Fernet (not plaintext).

## Needs human

- Configure Slack OAuth redirect URL and credentials; complete one install via `/slack/install?tenant_id=11111111-1111-1111-1111-111111111111` through the tunnel.

## Files changed

- `api/app/slack/crypto.py`, `store.py`, `routes.py`
- `pyproject.toml` (cryptography)

## API / webhook config

- Install: `{PUBLIC_BASE_URL}/slack/install?tenant_id=<uuid>`
- Callback: `{PUBLIC_BASE_URL}/slack/oauth/callback`

## Resume notes

Next batch: Task 4.4 — Mention + DM echo.

## Open questions

None.

## Smoke test results

- Upsert `TDEMO123` → tenant demo; decrypt round-trip ok; `GET /slack/installs/TDEMO123` → 200 without token
