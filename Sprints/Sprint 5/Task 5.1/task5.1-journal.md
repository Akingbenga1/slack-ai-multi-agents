# Task 5.1 journal

## Status

`completed`

## Summary

Celery app on Redis (`REDIS_URL`) with Worker + Beat entrypoints. Tasks module included; README + `docs/celery.md` document laptop-VPS run commands (Windows needs `--pool=solo`).

## Acceptance criteria checklist

- [x] Worker starts against Compose Redis — done (`--pool=solo` on Windows)
- [x] Beat starts — done
- [x] README documents both — done (`README.md`, `docs/celery.md`)

## Decision log

- App module: `worker.celery_app:celery_app`; tasks in `worker.tasks` via `include` + `import_default_modules()`.
- Windows: document `--pool=solo` (prefork billiard PermissionError on this host).

## Needs human

None for this task.

## Files changed

- `worker/celery_app.py`, `worker/__init__.py`, `worker/tasks.py` (stub → full in 5.3)
- `README.md`, `docs/celery.md`

## Resume notes

Continue Task 5.2 queues (same batch).

## Open questions

None.

## Smoke test results

- Worker ready on `redis://localhost:6379/0` with queues `high,default,low`
- Beat: `beat: Starting...`
