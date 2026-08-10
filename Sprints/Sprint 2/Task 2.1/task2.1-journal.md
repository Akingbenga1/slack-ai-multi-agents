# Task 2.1 journal

## Status

`completed`

## Summary

Added `api/app/settings.py` with Pydantic Settings covering DATABASE_URL, Redis, Qdrant, TEI, Slack, Stripe, JWT, PUBLIC_BASE_URL, Anthropic. Expanded `.env.example`. Health endpoint loads settings on request.

## Acceptance criteria checklist

- [x] Settings loads from env — done
- [x] Required keys present — done
- [x] `.env.example` documents keys — done

## Decision log

- Use `postgresql+psycopg://` dialect for SQLAlchemy/psycopg3.
- Host Postgres port **5433** (Compose maps 5433→5432) because something else already answered on host 5432 without role `csa`.

## Needs human

None.

## Files changed

- `api/app/settings.py`
- `api/app/main.py` (loads settings in `/health`)
- `.env.example`, `.env`
- `docker-compose.yml` (postgres host port 5433)
- `alembic.ini`

## Resume notes

Continue Task 2.2 migrations (done in same batch).

## Open questions

None.
