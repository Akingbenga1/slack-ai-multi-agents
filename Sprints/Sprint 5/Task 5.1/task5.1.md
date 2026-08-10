# Task 5.1 — Celery app + Redis broker

## Steps

- [x] Confirm Celery app uses Redis broker/backend from settings (`REDIS_URL`)
- [x] Wire Worker + Beat entrypoints (include / autodiscovers tasks)
- [x] Document how to run worker + beat on laptop-VPS (README)

## Acceptance criteria

- [x] `celery -A worker.celery_app worker` starts against Compose Redis
- [x] `celery -A worker.celery_app beat` starts
- [x] README documents both commands for laptop-as-VPS
