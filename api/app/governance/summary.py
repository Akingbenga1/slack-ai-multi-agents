"""Usage aggregates for org logs / usage API (Sprint 12.4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.app.billing.plans import get_tenant_entitlements, plan_is_active
from api.app.db.models import UsageEvent
from api.app.governance.budgets import sum_usage
from api.app.governance.usage import (
    JOB_BUDGET_EVENT_TYPES,
    TOKEN_BUDGET_EVENT_TYPES,
)

UsageWindow = Literal["day", "month"]


@dataclass(frozen=True)
class EventTypeAggregate:
    event_type: str
    event_count: int
    units: int


def _start_of_utc_day(now: datetime) -> datetime:
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)


def _start_of_utc_month(now: datetime) -> datetime:
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


def _window_start(window: UsageWindow, now: datetime) -> datetime:
    if window == "month":
        return _start_of_utc_month(now)
    return _start_of_utc_day(now)


def aggregate_usage_by_event_type(
    db: Session,
    tenant_id: UUID | str,
    *,
    since: datetime,
    until: Optional[datetime] = None,
) -> list[EventTypeAggregate]:
    """Group usage_events by event_type for tenant in [since, until)."""
    tid = UUID(str(tenant_id))
    q = (
        select(
            UsageEvent.event_type,
            func.count(UsageEvent.id),
            func.coalesce(func.sum(UsageEvent.units), 0),
        )
        .where(
            UsageEvent.tenant_id == tid,
            UsageEvent.created_at >= since,
        )
        .group_by(UsageEvent.event_type)
        .order_by(UsageEvent.event_type)
    )
    if until is not None:
        q = q.where(UsageEvent.created_at < until)

    rows = db.execute(q).all()
    return [
        EventTypeAggregate(
            event_type=str(event_type),
            event_count=int(count or 0),
            units=int(units or 0),
        )
        for event_type, count, units in rows
    ]


def _budget_slice(
    *,
    key: str,
    limit: int,
    used: int,
    window: str,
) -> dict:
    remaining = max(0, limit - used) if limit > 0 else 0
    return {
        "key": key,
        "limit": limit,
        "used": used,
        "remaining": remaining,
        "window": window,
    }


def budget_snapshot(
    db: Session,
    tenant_id: UUID | str,
    *,
    now: Optional[datetime] = None,
) -> dict:
    """Current plan budget headroom (same windows as Task 12.2)."""
    tid = UUID(str(tenant_id))
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    active = plan_is_active(db, tid)
    ents = get_tenant_entitlements(db, tid) if active else {}

    tokens_daily = int(ents.get("tokens_daily") or 0)
    tokens_monthly = int(ents.get("tokens_monthly") or 0)
    jobs_daily = int(ents.get("jobs_daily") or 0)

    used_tokens_d = (
        sum_usage(db, tid, TOKEN_BUDGET_EVENT_TYPES, since=_start_of_utc_day(now_utc))
        if tokens_daily > 0
        else 0
    )
    used_tokens_m = (
        sum_usage(db, tid, TOKEN_BUDGET_EVENT_TYPES, since=_start_of_utc_month(now_utc))
        if tokens_monthly > 0
        else 0
    )
    used_jobs = (
        sum_usage(db, tid, JOB_BUDGET_EVENT_TYPES, since=_start_of_utc_day(now_utc))
        if jobs_daily > 0
        else 0
    )

    return {
        "plan_active": active,
        "budgets": [
            _budget_slice(
                key="tokens_daily",
                limit=tokens_daily,
                used=used_tokens_d,
                window="daily",
            ),
            _budget_slice(
                key="tokens_monthly",
                limit=tokens_monthly,
                used=used_tokens_m,
                window="monthly",
            ),
            _budget_slice(
                key="jobs_daily",
                limit=jobs_daily,
                used=used_jobs,
                window="daily",
            ),
        ],
    }


def build_usage_summary(
    db: Session,
    tenant_id: UUID | str,
    *,
    window: UsageWindow = "day",
    now: Optional[datetime] = None,
) -> dict:
    """
    Tenant usage aggregates + budget snapshot for the org logs page.

    `window`: UTC calendar day or month.
    """
    tid = UUID(str(tenant_id))
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    since = _window_start(window, now_utc)
    by_type = aggregate_usage_by_event_type(db, tid, since=since, until=None)
    total_events = sum(a.event_count for a in by_type)
    total_units = sum(a.units for a in by_type)
    snap = budget_snapshot(db, tid, now=now_utc)

    return {
        "tenant_id": str(tid),
        "window": window,
        "since": since.isoformat().replace("+00:00", "Z"),
        "as_of": now_utc.isoformat().replace("+00:00", "Z"),
        "by_event_type": [
            {
                "event_type": a.event_type,
                "event_count": a.event_count,
                "units": a.units,
            }
            for a in by_type
        ],
        "totals": {
            "event_count": total_events,
            "units": total_units,
        },
        "plan_active": snap["plan_active"],
        "budgets": snap["budgets"],
    }
