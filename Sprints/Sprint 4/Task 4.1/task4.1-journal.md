# Task 4.1 journal

## Status

`completed`

## Summary

Wrote `docs/slack-app-setup.md` covering app creation, tunnel/`PUBLIC_BASE_URL`, Events URL, OAuth redirect, bot scopes, event subscriptions, install link, and private-channel invite note. Linked from tunnel plan + README.

## Acceptance criteria checklist

- [x] Checklist in `docs/` — done
- [x] Paths match implementation — done

## Decision log

- HTTP Events only (no Socket Mode).
- Minimum scopes for Sprint 4 echo; sync scopes deferred.

## Needs human

- Create Slack app at api.slack.com and set `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET` in `.env`.
- Run tunnel and set `PUBLIC_BASE_URL`; paste Events + OAuth URLs in Slack app config.
- Re-update Slack URLs if free tunnel hostname changes.

## Files changed

- `docs/slack-app-setup.md`
- `docs/tunnel-plan.md`
- `.env.example`, `README.md`

## Resume notes

Task 4.2 Events endpoint (done in same batch).

## Open questions

None.
