"""Celery queue names and routing helpers (tenant context + priority)."""

from __future__ import annotations

from typing import Any, Optional

# Named queues consumed by workers on the laptop-VPS.
QUEUE_HIGH = "high"
QUEUE_DEFAULT = "default"
QUEUE_LOW = "low"

ALL_QUEUES = (QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW)

# Job.priority (int) → queue. Higher priority number = more urgent.
PRIORITY_HIGH_MIN = 10
PRIORITY_LOW_MAX = -1


def queue_for_priority(priority: int = 0) -> str:
    """Map a numeric job priority to a Celery queue name."""
    if priority >= PRIORITY_HIGH_MIN:
        return QUEUE_HIGH
    if priority <= PRIORITY_LOW_MAX:
        return QUEUE_LOW
    return QUEUE_DEFAULT


def enqueue_options(
    *,
    client_id: Optional[str] = None,
    priority: int = 0,
    queue: Optional[str] = None,
    **extra: Any,
) -> dict[str, Any]:
    """
    Build Celery apply_async options: queue + tenant header.

    `client_id` is carried in task headers (see worker.celery_app signals).
    Queue is chosen from `priority` unless `queue` is set explicitly.
    """
    opts: dict[str, Any] = {
        "queue": queue or queue_for_priority(priority),
        **extra,
    }
    if client_id:
        headers = dict(opts.get("headers") or {})
        headers["client_id"] = client_id
        opts["headers"] = headers
    return opts
