# Task 1.2 — Python & Node toolchains

## Steps

- [x] Add root `pyproject.toml` + uv lock for Python 3.11+
- [x] Pin FastAPI, uvicorn, slack-bolt, langgraph, anthropic, qdrant-client, httpx, celery, redis, psycopg, pydantic-settings
- [x] Pin document parsers (PDF/DOCX/XLSX/CSV-related)
- [x] Include `api/`, `worker/`, `mcp_server` as installable packages
- [x] Scaffold Next.js App Router (TypeScript) under `web/`
- [x] Document install/run commands in README briefly

## Acceptance criteria

- [x] `uv sync` (or equivalent) installs Python deps from `pyproject.toml`
- [x] Required libraries are declared with pins/ranges in `pyproject.toml`
- [x] `web/` is a Next.js App Router TypeScript project that can install deps
