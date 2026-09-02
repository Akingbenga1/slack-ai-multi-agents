"""Usage / governance HTTP routes (Sprint 12.4 + 20.2 logs)."""

from __future__ import annotations

from typing import Annotated, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.app.auth.deps import require_tenant_access
from api.app.auth.tenant_resolve import resolve_tenant_uuid_for_principal
from api.app.auth.tokens import AuthPrincipal
from api.app.db.session import get_db
from api.app.governance.logs import (
    list_jobs,
    list_usage_events,
    serialize_job,
    serialize_usage_event,
)
from api.app.governance.summary import UsageWindow, build_usage_summary
from api.app.logging_config import get_logger

logger = get_logger("api.governance.routes")

router = APIRouter(prefix="/usage", tags=["usage"])


class EventTypeAggregateResponse(BaseModel):
    event_type: str
    event_count: int
    units: int


class UsageTotalsResponse(BaseModel):
    event_count: int
    units: int


class BudgetSliceResponse(BaseModel):
    key: str
    limit: int
    used: int
    remaining: int
    window: str


class UsageSummaryResponse(BaseModel):
    tenant_id: str
    window: Literal["day", "month"]
    since: str
    as_of: str
    by_event_type: list[EventTypeAggregateResponse]
    totals: UsageTotalsResponse
    plan_active: bool
    budgets: list[BudgetSliceResponse] = Field(default_factory=list)


class UsageEventItem(BaseModel):
    id: str
    event_type: str
    units: int
    meta: dict = Field(default_factory=dict)
    created_at: Optional[str] = None


class UsageEventsResponse(BaseModel):
    tenant_id: str
    events: list[UsageEventItem]
    total: int
    limit: int
    offset: int


class JobLogItem(BaseModel):
    id: str
    kind: str
    status: str
    error: Optional[str] = None
    created_at: Optional[str] = None
    finished_at: Optional[str] = None


class UsageJobsResponse(BaseModel):
    tenant_id: str
    jobs: list[JobLogItem]
    total: int
    limit: int
    offset: int


def _resolve_tenant_id(principal: AuthPrincipal) -> UUID:
    return resolve_tenant_uuid_for_principal(principal)


@router.get("/summary", response_model=UsageSummaryResponse)
def usage_summary(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    window: Annotated[
        UsageWindow,
        Query(description="UTC calendar day or month window"),
    ] = "day",
) -> UsageSummaryResponse:
    """Aggregated usage_events + budget headroom for the current tenant."""
    tid = _resolve_tenant_id(principal)
    payload = build_usage_summary(db, tid, window=window)
    logger.info(
        "usage_summary tenant_id=%s window=%s events=%s",
        tid,
        window,
        payload["totals"]["event_count"],
    )
    return UsageSummaryResponse(**payload)


@router.get("/events", response_model=UsageEventsResponse)
def usage_events(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    event_type: Annotated[
        Optional[str],
        Query(description="Optional filter: slack_mention, llm_tokens, job, …"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UsageEventsResponse:
    """Recent usage_events for the org logs page (OR-07)."""
    tid = _resolve_tenant_id(principal)
    rows, total = list_usage_events(
        db, tid, event_type=event_type, limit=limit, offset=offset,
    )
    return UsageEventsResponse(
        tenant_id=str(tid),
        events=[UsageEventItem(**serialize_usage_event(r)) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/jobs", response_model=UsageJobsResponse)
def usage_jobs(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[
        Optional[str],
        Query(alias="status", description="Optional filter e.g. failed"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UsageJobsResponse:
    """Recent jobs rows (errors when status=failed) for the org logs page."""
    tid = _resolve_tenant_id(principal)
    rows, total = list_jobs(
        db, tid, status=status_filter, limit=limit, offset=offset,
    )
    return UsageJobsResponse(
        tenant_id=str(tid),
        jobs=[JobLogItem(**serialize_job(r)) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
