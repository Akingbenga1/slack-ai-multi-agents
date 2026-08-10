# Task 1.2 journal

## Status

`completed`

## Summary

Added root `pyproject.toml` with uv; `uv sync` resolved and installed pinned FastAPI stack, LangGraph, Anthropic, Qdrant, Celery/Redis, psycopg, pydantic-settings, and doc parsers. Scaffolded Next.js 15 App Router (TypeScript) under `web/` via create-next-app.

## Acceptance criteria checklist

- [x] `uv sync` installs Python deps — done
- [x] Required libraries declared with version ranges — done
- [x] `web/` is Next.js App Router TypeScript — done

## Decision log

- Single root Python package (`client-slack-agents`) via hatchling packaging `api`, `worker`, `mcp_server` — simpler than multi-workspace for Sprint 1.
- Embedding/doc parsers: `pypdf`, `python-docx`, `openpyxl`, `pandas` (CSV).
- Next.js 15 with App Router, ESLint, no Tailwind (product UI styling later), npm.

## Needs human

None.

## Files changed

- `pyproject.toml`, `uv.lock`, `.venv/` (local)
- `web/` (Next.js scaffold)
- `README.md` (setup commands)

## Resume notes

Continue with Task 1.3 (Docker Compose + `.env.example`).

## Open questions

None.

## Smoke test results

- `uv sync` succeeded (88 packages).
- `create-next-app` + npm install succeeded.
