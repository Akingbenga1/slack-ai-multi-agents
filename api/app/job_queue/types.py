"""Vendor-neutral enqueue result (Sprint 38)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnqueueResult:
    """Product-facing handle for an enqueued job (no Celery ``AsyncResult``)."""

    task_id: str
    queue: str
    kind: str

    @property
    def id(self) -> str:
        """Alias for callers that historically used Celery ``AsyncResult.id``."""
        return self.task_id
