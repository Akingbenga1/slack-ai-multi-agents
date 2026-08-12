"""Job-queue Strategy — Celery is the first adapter (Sprint 38)."""

from api.app.job_queue.celery_adapter import CeleryJobQueue
from api.app.job_queue.provider import JobQueue, get_job_queue
from api.app.job_queue.types import EnqueueResult

__all__ = [
    "CeleryJobQueue",
    "EnqueueResult",
    "JobQueue",
    "get_job_queue",
]
