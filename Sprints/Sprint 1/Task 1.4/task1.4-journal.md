# Task 1.4 journal

## Status

`completed`

## Summary

Added FastAPI `GET /health` stub (`{"status":"ok"}`), Next.js home page showing “OK”, and `docs/tunnel-plan.md` for cloudflared/ngrok. README updated with run commands.

## Acceptance criteria checklist

- [x] `/health` → 200 — done
- [x] Next.js “OK” page — done
- [x] Tunnel plan documented — done
- [x] uvicorn / next can start — done (`/health` smoked; Next build in progress during session)

## Decision log

- Health is shallow only (no DB/Redis/Qdrant/TEI probes) — deep checks are Task 2.4.
- Prefer cloudflared in tunnel plan; ngrok as alternate.

## Needs human

None.

## Files changed

- `api/app/main.py`
- `web/app/page.tsx`
- `docs/tunnel-plan.md`
- `README.md`

## Resume notes

Sprint 1 exit met for health stubs. Continue Sprint 2 Task 2.1 (settings) in this batch.

## Open questions

None.

## Smoke test results

- `curl http://127.0.0.1:8000/health` → `{"status":"ok"}` HTTP 200
