"""Internal job trigger stubs (Sprint 5 + Slack sync enqueue)."""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.app.auth.deps import require_tenant_access
from api.app.auth.tokens import AuthPrincipal
from api.app.billing.plans import require_entitlement
from api.app.db.session import get_db
from api.app.governance.budgets import require_budget
from api.app.reports.schedule import (
    get_recurring_report_schedule,
    normalize_cadence,
    set_recurring_report_schedule,
)
from api.app.slack.schedule import (
    is_slack_history_sync_enabled,
    set_slack_history_sync_enabled,
)
from api.app.slack.sync_status import get_slack_history_sync_status
from api.app.tenant import get_client_id
from worker.queues import queue_for_priority
from worker.tasks import (
    enqueue_heartbeat,
    enqueue_recurring_report,
    enqueue_slack_history_sync,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


class HeartbeatEnqueueRequest(BaseModel):
    """Optional overrides. Tenant usually comes from JWT / X-Client-Id."""

    tenant_id: Optional[str] = Field(
        default=None,
        description="Target tenant (platform_owner may set; org_admin must match membership)",
    )
    message: str = Field(default="ok", min_length=1, max_length=200)
    priority: int = Field(default=0, description="Maps to high/default/low queue")


class HeartbeatEnqueueResponse(BaseModel):
    task_id: str
    client_id: str
    queue: str
    kind: str = "heartbeat"


class SlackHistorySyncEnqueueRequest(BaseModel):
    tenant_id: Optional[str] = Field(
        default=None,
        description="Target tenant (platform_owner may set; org_admin must match membership)",
    )
    channel_ids: Optional[list[str]] = Field(
        default=None,
        description="Optional channel filter; omit to sync all listable channels",
    )
    priority: int = Field(
        default=-1,
        description="Maps to high/default/low queue (default -1 → low)",
    )


class SlackHistorySyncEnqueueResponse(BaseModel):
    task_id: str
    client_id: str
    queue: str
    kind: str = "slack_history_sync"


class SlackHistorySyncScheduleResponse(BaseModel):
    client_id: str
    enabled: bool
    kind: str = "slack_history_sync"


class SlackHistorySyncScheduleUpdate(BaseModel):
    tenant_id: Optional[str] = Field(
        default=None,
        description="Target tenant (platform_owner may set; org_admin must match membership)",
    )
    enabled: bool = Field(description="When false, hourly Beat skips this tenant")


class SlackHistorySyncStatusResponse(BaseModel):
    client_id: str
    kind: str = "slack_history_sync"
    enabled: bool
    slack_connected: bool
    last_success: Optional[dict] = None
    last_failure: Optional[dict] = None
    last_job: Optional[dict] = None
    watermarks: dict


class RecurringReportScheduleResponse(BaseModel):
    client_id: str
    kind: str = "recurring_report"
    enabled: bool
    channel_id: Optional[str] = None
    cadence: str
    window_label: str


class RecurringReportScheduleUpdate(BaseModel):
    tenant_id: Optional[str] = Field(
        default=None,
        description="Target tenant (platform_owner may set; org_admin must match membership)",
    )
    enabled: Optional[bool] = Field(
        default=None,
        description="When false, Beat skips this tenant's recurring report",
    )
    channel_id: Optional[str] = Field(
        default=None,
        description="Slack channel id for direct report posts",
    )
    clear_channel: bool = Field(
        default=False,
        description="When true, unset channel_id",
    )
    cadence: Optional[str] = Field(
        default=None,
        description="daily or weekly",
    )
    window_label: Optional[str] = Field(
        default=None,
        description="Optional override (default derived from cadence)",
    )


class RecurringReportEnqueueRequest(BaseModel):
    tenant_id: Optional[str] = Field(
        default=None,
        description="Target tenant (platform_owner may set; org_admin must match membership)",
    )
    channel_id: Optional[str] = Field(
        default=None,
        description="Override schedule channel; omit to use saved channel_id",
    )
    window_label: Optional[str] = Field(
        default=None,
        description="Override digest window label",
    )
    prefer_sync: bool = Field(
        default=True,
        description="Sync the target channel before generating the report",
    )
    priority: int = Field(default=0, description="Maps to high/default/low queue")


class RecurringReportEnqueueResponse(BaseModel):
    task_id: str
    client_id: str
    queue: str
    kind: str = "recurring_report"


def _resolve_enqueue_tenant(
    principal: AuthPrincipal,
    body_tenant_id: Optional[str],
) -> str:
    """Tenant for enqueue: context (JWT/header) preferred; body for platform_owner."""
    from_ctx = get_client_id() or principal.tenant_id
    requested = (body_tenant_id or "").strip() or None

    if principal.all_access or principal.role == "platform_owner":
        chosen = requested or from_ctx
        if not chosen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tenant_id required (body.tenant_id or X-Client-Id)",
            )
        try:
            return str(UUID(chosen))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tenant id",
            ) from exc

    if not from_ctx:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Org user has no tenant membership",
        )

    try:
        allowed = str(UUID(from_ctx))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant id",
        ) from exc

    if requested:
        try:
            if str(UUID(requested)) != allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cross-tenant access denied",
                )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tenant id",
            ) from exc

    return allowed


@router.post("/heartbeat", response_model=HeartbeatEnqueueResponse)
def enqueue_tenant_heartbeat(
    body: HeartbeatEnqueueRequest,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> HeartbeatEnqueueResponse:
    """
    Internal stub: enqueue a tenant heartbeat job (auth required).

    Does not wait for the worker; returns Celery task id immediately.
    """
    client_id = _resolve_enqueue_tenant(principal, body.tenant_id)
    require_budget(db, client_id, "jobs", units=1)
    async_result = enqueue_heartbeat(
        client_id=client_id,
        message=body.message,
        priority=body.priority,
    )
    return HeartbeatEnqueueResponse(
        task_id=async_result.id,
        client_id=client_id,
        queue=queue_for_priority(body.priority),
    )


@router.post("/slack-history-sync", response_model=SlackHistorySyncEnqueueResponse)
def enqueue_tenant_slack_history_sync(
    body: SlackHistorySyncEnqueueRequest,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> SlackHistorySyncEnqueueResponse:
    """
    On-demand live Slack history sync (auth required).

    Bypasses Beat enable/disable; always enqueues for the caller's tenant.
    Does not wait for the worker; returns Celery task id immediately.
    """
    client_id = _resolve_enqueue_tenant(principal, body.tenant_id)
    require_entitlement(db, client_id, "sync")
    require_budget(db, client_id, "jobs", units=1, require_active_plan=True)
    async_result = enqueue_slack_history_sync(
        client_id=client_id,
        channel_ids=body.channel_ids,
        priority=body.priority,
    )
    return SlackHistorySyncEnqueueResponse(
        task_id=async_result.id,
        client_id=client_id,
        queue=queue_for_priority(body.priority),
    )


@router.get(
    "/slack-history-sync/schedule",
    response_model=SlackHistorySyncScheduleResponse,
)
def get_slack_history_sync_schedule(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    tenant_id: Optional[str] = None,
) -> SlackHistorySyncScheduleResponse:
    """Read whether hourly Beat will enqueue sync for the tenant."""
    client_id = _resolve_enqueue_tenant(principal, tenant_id)
    enabled = is_slack_history_sync_enabled(db, UUID(client_id))
    return SlackHistorySyncScheduleResponse(client_id=client_id, enabled=enabled)


@router.patch(
    "/slack-history-sync/schedule",
    response_model=SlackHistorySyncScheduleResponse,
)
def patch_slack_history_sync_schedule(
    body: SlackHistorySyncScheduleUpdate,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> SlackHistorySyncScheduleResponse:
    """Enable or disable hourly Beat sync for the tenant (on-demand still allowed)."""
    client_id = _resolve_enqueue_tenant(principal, body.tenant_id)
    set_slack_history_sync_enabled(db, tenant_id=UUID(client_id), enabled=body.enabled)
    return SlackHistorySyncScheduleResponse(client_id=client_id, enabled=body.enabled)


@router.get(
    "/slack-history-sync/status",
    response_model=SlackHistorySyncStatusResponse,
)
def get_tenant_slack_history_sync_status(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    tenant_id: Optional[str] = None,
) -> SlackHistorySyncStatusResponse:
    """Last success/failure (+ watermarks) for live Slack history sync (portal)."""
    client_id = _resolve_enqueue_tenant(principal, tenant_id)
    payload = get_slack_history_sync_status(db, UUID(client_id))
    return SlackHistorySyncStatusResponse(**payload)


@router.get(
    "/recurring-report/schedule",
    response_model=RecurringReportScheduleResponse,
)
def get_recurring_report_schedule_api(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    tenant_id: Optional[str] = None,
) -> RecurringReportScheduleResponse:
    """Read recurring report channel / cadence / enable for the tenant."""
    client_id = _resolve_enqueue_tenant(principal, tenant_id)
    sched = get_recurring_report_schedule(db, UUID(client_id))
    return RecurringReportScheduleResponse(
        client_id=client_id,
        enabled=bool(sched["enabled"]),
        channel_id=sched.get("channel_id"),
        cadence=str(sched["cadence"]),
        window_label=str(sched["window_label"]),
    )


@router.patch(
    "/recurring-report/schedule",
    response_model=RecurringReportScheduleResponse,
)
def patch_recurring_report_schedule_api(
    body: RecurringReportScheduleUpdate,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> RecurringReportScheduleResponse:
    """Update recurring report schedule (channel + cadence + enable)."""
    client_id = _resolve_enqueue_tenant(principal, body.tenant_id)
    if body.cadence is not None:
        try:
            normalize_cadence(body.cadence)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
    set_recurring_report_schedule(
        db,
        tenant_id=UUID(client_id),
        enabled=body.enabled,
        channel_id=body.channel_id,
        cadence=body.cadence,
        window_label=body.window_label,
        clear_channel=body.clear_channel,
    )
    sched = get_recurring_report_schedule(db, UUID(client_id))
    return RecurringReportScheduleResponse(
        client_id=client_id,
        enabled=bool(sched["enabled"]),
        channel_id=sched.get("channel_id"),
        cadence=str(sched["cadence"]),
        window_label=str(sched["window_label"]),
    )


@router.post("/recurring-report", response_model=RecurringReportEnqueueResponse)
def enqueue_tenant_recurring_report(
    body: RecurringReportEnqueueRequest,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> RecurringReportEnqueueResponse:
    """
    Force a recurring report now (auth required).

    Bypasses Beat enable/disable; uses schedule channel when body.channel_id
    omitted. Does not wait for the worker.
    """
    client_id = _resolve_enqueue_tenant(principal, body.tenant_id)
    sched = get_recurring_report_schedule(db, UUID(client_id))
    channel = (body.channel_id or sched.get("channel_id") or "").strip()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="channel_id required (body or saved schedule)",
        )
    require_entitlement(db, client_id, "agent")
    require_budget(db, client_id, "jobs", units=1, require_active_plan=True)
    async_result = enqueue_recurring_report(
        client_id=client_id,
        channel_id=channel,
        window_label=body.window_label or sched.get("window_label"),
        prefer_sync=body.prefer_sync,
        priority=body.priority,
    )
    return RecurringReportEnqueueResponse(
        task_id=async_result.id,
        client_id=client_id,
        queue=queue_for_priority(body.priority),
    )
