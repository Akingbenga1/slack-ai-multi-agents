"""Plan token/job budget checks (Sprint 12.2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.app.billing.plans import get_tenant_entitlements, plan_is_active
from api.app.db.models import UsageEvent
from api.app.governance.usage import (
    JOB_BUDGET_EVENT_TYPES,
    TOKEN_BUDGET_EVENT_TYPES,
)
from api.app.logging_config import get_logger

logger = get_logger("api.governance.budgets")

BudgetResource = Literal["tokens", "jobs"]


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    resource: BudgetResource
    limit: int
    used: int
    remaining: int
    window: str  # daily | monthly | none
    reason: str = ""  # ok | budget_exceeded | plan_inactive | no_budget


def _start_of_utc_day(now: datetime) -> datetime:
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)


def _start_of_utc_month(now: datetime) -> datetime:
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


def sum_usage(
    db: Session,
    tenant_id: UUID | str,
    event_types: set[str] | frozenset[str],
    *,
    since: datetime,
) -> int:
    """Sum `units` for tenant + event types since `since` (inclusive)."""
    tid = UUID(str(tenant_id))
    total = db.scalar(
        select(func.coalesce(func.sum(UsageEvent.units), 0)).where(
            UsageEvent.tenant_id == tid,
            UsageEvent.event_type.in_(tuple(event_types)),
            UsageEvent.created_at >= since,
        )
    )
    return int(total or 0)


def check_budget(
    db: Session,
    tenant_id: UUID | str,
    resource: BudgetResource,
    *,
    units: int = 1,
    now: Optional[datetime] = None,
    require_active_plan: bool = False,
) -> BudgetDecision:
    """
    Allow/deny based on plan entitlements and usage_events in the budget window.

    - `tokens`: checks daily then monthly caps (`tokens_daily` / `tokens_monthly`)
    - `jobs`: checks `jobs_daily`

    When the plan is inactive:
    - `require_active_plan=False` (default) → allow (Sprint 14 handles agent messaging)
    - `require_active_plan=True` → deny with `plan_inactive`
    """
    tid = UUID(str(tenant_id))
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    units_i = max(0, int(units))

    if not plan_is_active(db, tid):
        if require_active_plan:
            return BudgetDecision(
                allowed=False,
                resource=resource,
                limit=0,
                used=0,
                remaining=0,
                window="none",
                reason="plan_inactive",
            )
        return BudgetDecision(
            allowed=True,
            resource=resource,
            limit=0,
            used=0,
            remaining=0,
            window="none",
            reason="plan_inactive",
        )

    ents = get_tenant_entitlements(db, tid)

    if resource == "tokens":
        return _check_token_budgets(db, tid, ents, units_i, now_utc)
    return _check_job_budget(db, tid, ents, units_i, now_utc)


def _check_job_budget(
    db: Session,
    tenant_id: UUID,
    ents: dict,
    units: int,
    now: datetime,
) -> BudgetDecision:
    limit = int(ents.get("jobs_daily") or 0)
    if limit <= 0:
        return BudgetDecision(
            allowed=False,
            resource="jobs",
            limit=0,
            used=0,
            remaining=0,
            window="daily",
            reason="no_budget",
        )
    since = _start_of_utc_day(now)
    used = sum_usage(db, tenant_id, JOB_BUDGET_EVENT_TYPES, since=since)
    remaining = max(0, limit - used)
    if used + units > limit:
        logger.warning(
            "budget_exceeded resource=jobs tenant_id=%s used=%s units=%s limit=%s",
            tenant_id,
            used,
            units,
            limit,
        )
        return BudgetDecision(
            allowed=False,
            resource="jobs",
            limit=limit,
            used=used,
            remaining=remaining,
            window="daily",
            reason="budget_exceeded",
        )
    return BudgetDecision(
        allowed=True,
        resource="jobs",
        limit=limit,
        used=used,
        remaining=max(0, remaining - units),
        window="daily",
        reason="ok",
    )


def _check_token_budgets(
    db: Session,
    tenant_id: UUID,
    ents: dict,
    units: int,
    now: datetime,
) -> BudgetDecision:
    daily_limit = int(ents.get("tokens_daily") or 0)
    monthly_limit = int(ents.get("tokens_monthly") or 0)
    if daily_limit <= 0 and monthly_limit <= 0:
        return BudgetDecision(
            allowed=False,
            resource="tokens",
            limit=0,
            used=0,
            remaining=0,
            window="none",
            reason="no_budget",
        )

    # Prefer the tighter remaining headroom across daily + monthly windows.
    decisions: list[BudgetDecision] = []
    if daily_limit > 0:
        used_d = sum_usage(
            db, tenant_id, TOKEN_BUDGET_EVENT_TYPES, since=_start_of_utc_day(now)
        )
        rem_d = max(0, daily_limit - used_d)
        ok_d = used_d + units <= daily_limit
        decisions.append(
            BudgetDecision(
                allowed=ok_d,
                resource="tokens",
                limit=daily_limit,
                used=used_d,
                remaining=rem_d if not ok_d else max(0, rem_d - units),
                window="daily",
                reason="ok" if ok_d else "budget_exceeded",
            )
        )
    if monthly_limit > 0:
        used_m = sum_usage(
            db, tenant_id, TOKEN_BUDGET_EVENT_TYPES, since=_start_of_utc_month(now)
        )
        rem_m = max(0, monthly_limit - used_m)
        ok_m = used_m + units <= monthly_limit
        decisions.append(
            BudgetDecision(
                allowed=ok_m,
                resource="tokens",
                limit=monthly_limit,
                used=used_m,
                remaining=rem_m if not ok_m else max(0, rem_m - units),
                window="monthly",
                reason="ok" if ok_m else "budget_exceeded",
            )
        )

    # If any window blocks, return the blocking decision (prefer daily in ties).
    for d in decisions:
        if not d.allowed:
            logger.warning(
                "budget_exceeded resource=tokens window=%s tenant_id=%s used=%s "
                "units=%s limit=%s",
                d.window,
                tenant_id,
                d.used,
                units,
                d.limit,
            )
            return d
    # All allowed — return the tighter remaining window
    return min(decisions, key=lambda d: d.remaining)


def budget_http_detail(decision: BudgetDecision) -> dict:
    return {
        "detail": decision.reason or "budget_exceeded",
        "resource": decision.resource,
        "limit": decision.limit,
        "used": decision.used,
        "remaining": decision.remaining,
        "window": decision.window,
    }


def require_budget(
    db: Session,
    tenant_id: UUID | str,
    resource: BudgetResource,
    *,
    units: int = 1,
    require_active_plan: bool = False,
) -> BudgetDecision:
    """Raise HTTPException 403 when over budget (or inactive if require_active_plan)."""
    from fastapi import HTTPException, status

    decision = check_budget(
        db,
        tenant_id,
        resource,
        units=units,
        require_active_plan=require_active_plan,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=budget_http_detail(decision),
        )
    return decision
