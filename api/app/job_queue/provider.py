"""Job-queue Strategy + Factory (Sprint 38).

Product jobs know only ``JobQueue.enqueue(kind, tenant_id, payload)``. Celery
(and later RQ / Dramatiq) live in adapters; ``get_job_queue`` selects by
``JOB_QUEUE``. Sprint 29 ``@tenant_job`` / ``jobs`` rows stay the lifecycle
contract — this Strategy only owns *enqueue*.
"""

from __future__ import annotations

from typing import Any, Protocol

from api.app.job_queue.types import EnqueueResult
from api.app.settings import Settings, get_settings


class JobQueue(Protocol):
    """Vendor-neutral tenant job enqueue."""

    @property
    def name(self) -> str:
        """Adapter id (e.g. ``celery``)."""
        ...

    def enqueue(
        self,
        *,
        kind: str,
        tenant_id: str,
        payload: dict[str, Any] | None = None,
    ) -> EnqueueResult:
        """Enqueue a job by product ``kind`` for ``tenant_id``."""
        ...


def get_job_queue(settings: Settings | None = None) -> JobQueue:
    """Factory: select job-queue adapter by ``JOB_QUEUE`` (default ``celery``)."""
    settings = settings or get_settings()
    name = (settings.job_queue or "celery").strip().lower()
    if name == "celery":
        from api.app.job_queue.celery_adapter import CeleryJobQueue

        return CeleryJobQueue(settings)
    if name in ("rq", "dramatiq"):
        raise ValueError(
            f"{name} job-queue adapter is not implemented — set JOB_QUEUE=celery "
            "(documented extension only)"
        )
    raise ValueError(f"Unknown JOB_QUEUE={name!r}; expected celery|rq|dramatiq")
