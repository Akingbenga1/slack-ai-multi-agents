"""Tenant Celery job Template Method (Sprint 29.2).

Skeleton: resolve tenant → session → create/running → body → succeed + usage
(or fail + optional fail usage) → close.
Domain tasks supply only the body Strategy.
"""

from __future__ import annotations

import functools
import logging
import uuid
from dataclasses import dataclass, field
from collections.abc import Sequence
from typing import Any, Callable, Optional, TypeVar

from sqlalchemy.orm import Session

from api.app.db.models import Job
from api.app.governance.usage import record_usage
from api.app.membership import DEMO_TENANT_ID
from api.app.tenant import get_client_id, set_client_id
from worker.job_meta import (
    create_job,
    mark_failed,
    mark_running,
    mark_succeeded,
    session_scope,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def resolve_tenant_id(tenant_id: Optional[str] = None) -> uuid.UUID:
    """Prefer Celery header context; fall back to kwarg / demo tenant."""
    client_id = get_client_id() or tenant_id
    if not client_id:
        client_id = str(DEMO_TENANT_ID)
        set_client_id(client_id)
    try:
        tenant_uuid = uuid.UUID(str(client_id))
    except ValueError as exc:
        raise ValueError(f"Invalid tenant_id/client_id: {client_id!r}") from exc
    set_client_id(str(tenant_uuid))
    return tenant_uuid


@dataclass
class TenantJobContext:
    """Runtime handle for a tenant job body (db / job / usage hooks)."""

    db: Session
    tenant_id: uuid.UUID
    job: Job
    task_id: str | None
    usage_units: int = 1
    usage_meta: dict[str, Any] = field(default_factory=dict)
    skip_usage: bool = False

    def set_usage(
        self,
        *,
        units: int = 1,
        meta: dict[str, Any] | None = None,
        skip: bool = False,
    ) -> None:
        self.usage_units = units
        self.skip_usage = skip
        if meta is not None:
            self.usage_meta = meta


def run_tenant_job(
    task: Any,
    *,
    kind: str,
    usage_event: str,
    tenant_id: Optional[str],
    priority: int,
    payload: dict[str, Any],
    body: Callable[[TenantJobContext], dict[str, Any]],
    fail_usage_event: str | None = None,
    log_label: str | None = None,
) -> dict[str, Any]:
    """
    Shared job lifecycle Template Method.

    ``body(ctx)`` performs domain work and returns the result dict.
    Call ``ctx.set_usage(...)`` inside the body to customize success usage.
    """
    label = log_label or kind
    tenant_uuid = resolve_tenant_id(tenant_id)
    task_id = getattr(getattr(task, "request", None), "id", None)
    logger.info(
        "%s start task_id=%s client_id=%s",
        label,
        task_id,
        tenant_uuid,
    )

    db = session_scope()
    job: Job | None = None
    try:
        job = create_job(
            db,
            tenant_id=tenant_uuid,
            kind=kind,
            priority=priority,
            payload=payload,
        )
        mark_running(db, job)
        ctx = TenantJobContext(
            db=db,
            tenant_id=tenant_uuid,
            job=job,
            task_id=task_id,
            usage_meta={"kind": kind, "job_id": str(job.id)},
        )
        result = body(ctx)
        if not isinstance(result, dict):
            raise TypeError(f"{label} body must return dict, got {type(result)!r}")
        result.setdefault("job_id", str(job.id))
        if task_id is not None:
            result.setdefault("task_id", task_id)
        mark_succeeded(db, job, result=result)
        if not ctx.skip_usage:
            meta = dict(ctx.usage_meta)
            meta.setdefault("kind", kind)
            meta.setdefault("job_id", str(job.id))
            record_usage(
                db,
                tenant_uuid,
                usage_event,
                units=ctx.usage_units,
                meta=meta,
                commit=True,
            )
        logger.info(
            "%s ok job_id=%s status=succeeded client_id=%s",
            label,
            job.id,
            tenant_uuid,
        )
        return result
    except Exception as exc:
        if job is not None:
            mark_failed(db, job, str(exc))
            if fail_usage_event:
                try:
                    record_usage(
                        db,
                        tenant_uuid,
                        fail_usage_event,
                        units=1,
                        meta={
                            "kind": kind,
                            "job_id": str(job.id),
                            "status": "failed",
                            "error": str(exc)[:500],
                        },
                        commit=True,
                    )
                except Exception:
                    logger.exception("%s usage_record_failed", label)
        logger.exception("%s failed", label)
        raise
    finally:
        db.close()


def tenant_job(
    *,
    kind: str,
    usage_event: str,
    fail_usage_event: str | None = None,
    log_label: str | None = None,
) -> Callable[[F], F]:
    """
    Decorator for ``bind=True`` Celery tasks.

    Injects ``TenantJobContext`` as the second positional arg (after ``self``).
    Job payload = non-lifecycle kwargs + ``celery_task_id``.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(
            self: Any,
            *args: Any,
            tenant_id: Optional[str] = None,
            priority: int = 0,
            **kwargs: Any,
        ) -> dict[str, Any]:
            task_id = getattr(getattr(self, "request", None), "id", None)
            payload = {"celery_task_id": task_id, **kwargs}

            def body(ctx: TenantJobContext) -> dict[str, Any]:
                return fn(
                    self,
                    ctx,
                    *args,
                    tenant_id=tenant_id,
                    priority=priority,
                    **kwargs,
                )

            return run_tenant_job(
                self,
                kind=kind,
                usage_event=usage_event,
                tenant_id=tenant_id,
                priority=priority,
                payload=payload,
                body=body,
                fail_usage_event=fail_usage_event,
                log_label=log_label,
            )

        return wrapper  # type: ignore[return-value]

    return decorator


def run_dispatch(
    task: Any,
    *,
    list_due: Callable[[Any], Sequence[Any]],
    enqueue_row: Callable[[Any], dict[str, Any]],
    log_label: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Thin Beat dispatcher Template Method.

    ``list_due(db)`` returns due tenants/rows; ``enqueue_row(item)`` enqueues
    and returns a serializable dict for the response.
    """
    task_id = getattr(getattr(task, "request", None), "id", None)
    db = session_scope()
    try:
        due = list(list_due(db))
        enqueued = [enqueue_row(item) for item in due]
        logger.info(
            "%s task_id=%s enqueued=%s",
            log_label,
            task_id,
            len(enqueued),
        )
        result: dict[str, Any] = {
            "task_id": task_id,
            "count": len(enqueued),
            "enqueued": enqueued,
        }
        if extra:
            result.update(extra)
        return result
    finally:
        db.close()


# Back-compat alias used by older tests / imports.
_resolve_tenant_id = resolve_tenant_id
