"""Per-tenant recurring report schedule (channel + cadence + enable).

Persistence: ``ScheduleStore``. Kind rules: ``RecurringReportStrategy``.
"""

from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.db.models import AgentConfig
from api.app.schedules.kinds import (
    RECURRING_REPORT_KEY,
    Cadence,
    get_schedule_kind,
    list_due_recurring_reports,
    normalize_cadence,
    period_key_for_cadence,
    window_label_for_cadence,
)
from api.app.schedules.service import patch_kind, read_kind
from api.app.schedules.store import DEFAULT_AGENT_NAME, get_block, upsert_block

SCHEDULE_KEY = RECURRING_REPORT_KEY
DEFAULT_ENABLED = False
DEFAULT_CADENCE: Literal["daily", "weekly"] = "weekly"


def get_recurring_report_schedule(db: Session, tenant_id: UUID) -> dict[str, Any]:
    """
    Return normalized schedule fields for the tenant.

    Defaults: enabled=False, cadence=weekly, channel_id=None,
    window_label derived from cadence.
    """
    return read_kind(db, tenant_id, SCHEDULE_KEY)


def is_recurring_report_enabled(db: Session, tenant_id: UUID) -> bool:
    return bool(get_recurring_report_schedule(db, tenant_id)["enabled"])


def set_recurring_report_schedule(
    db: Session,
    *,
    tenant_id: UUID,
    enabled: bool | None = None,
    channel_id: str | None = None,
    cadence: str | None = None,
    window_label: str | None = None,
    clear_channel: bool = False,
) -> AgentConfig:
    """
    Upsert ``agent_configs.schedules.recurring_report`` fields.

    Pass ``clear_channel=True`` to unset ``channel_id``. Omit a field to leave
    it unchanged (or default on create).
    """
    patch: dict[str, Any] = {"clear_channel": clear_channel}
    if enabled is not None:
        patch["enabled"] = enabled
    if channel_id is not None:
        patch["channel_id"] = channel_id
    if cadence is not None:
        patch["cadence"] = cadence
    if window_label is not None:
        patch["window_label"] = window_label
    return patch_kind(
        db,
        tenant_id=tenant_id,
        key=SCHEDULE_KEY,
        patch=patch,
    )


def claim_recurring_report_period(
    db: Session,
    *,
    tenant_id: UUID,
    force: bool = False,
    when: Optional[Any] = None,
) -> tuple[bool, str, dict[str, Any]]:
    """
    Atomically claim the current cadence period before posting.

    Returns ``(claimed, period, schedule)``. When ``claimed`` is False the
    period was already taken (unless ``force``). On claim, writes
    ``last_posted_period`` immediately so concurrent Beat workers skip.
    """
    from datetime import datetime, timezone

    moment = when or datetime.now(timezone.utc)
    if isinstance(moment, datetime) and moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)

    current = get_block(db, tenant_id, SCHEDULE_KEY, for_update=True)
    strategy = get_schedule_kind(SCHEDULE_KEY)
    sched = strategy.normalize(current)
    period = period_key_for_cadence(sched["cadence"], when=moment)
    if not force and sched.get("last_posted_period") == period:
        return False, period, sched

    block = strategy.apply_patch(
        current,
        {
            "last_posted_period": period,
            "last_posted_at": moment.isoformat(),
        },
    )
    upsert_block(
        db,
        tenant_id=tenant_id,
        key=SCHEDULE_KEY,
        block=block,
        merge=False,
        commit=True,
    )
    return True, period, strategy.normalize(block)


def release_recurring_report_period_claim(
    db: Session,
    *,
    tenant_id: UUID,
    period: str,
) -> None:
    """Clear a failed claim so Beat can retry the same period."""
    current = get_block(db, tenant_id, SCHEDULE_KEY, for_update=True)
    strategy = get_schedule_kind(SCHEDULE_KEY)
    sched = strategy.normalize(current)
    if sched.get("last_posted_period") != period:
        return
    block = dict(sched)
    block.pop("last_posted_period", None)
    block.pop("last_posted_at", None)
    upsert_block(
        db,
        tenant_id=tenant_id,
        key=SCHEDULE_KEY,
        block=block,
        merge=False,
        commit=True,
    )


def mark_recurring_report_posted(
    db: Session,
    *,
    tenant_id: UUID,
    when: Optional[Any] = None,
    period: str | None = None,
) -> dict[str, Any]:
    """
    Confirm Beat idempotency markers after a successful Slack post.

    Usually a no-op after ``claim_recurring_report_period``; refreshes
    ``last_posted_at`` and ensures ``last_posted_period`` is set.
    """
    from datetime import datetime, timezone

    moment = when or datetime.now(timezone.utc)
    current = get_block(db, tenant_id, SCHEDULE_KEY, for_update=True)
    strategy = get_schedule_kind(SCHEDULE_KEY)
    sched = strategy.normalize(current)
    resolved_period = period or period_key_for_cadence(sched["cadence"], when=moment)
    block = strategy.apply_patch(
        current,
        {
            "last_posted_period": resolved_period,
            "last_posted_at": moment.isoformat(),
        },
    )
    upsert_block(
        db,
        tenant_id=tenant_id,
        key=SCHEDULE_KEY,
        block=block,
        merge=False,
        commit=True,
    )
    return {"period": resolved_period, "last_posted_at": block["last_posted_at"]}


def list_tenants_for_scheduled_reports(
    db: Session,
    *,
    cadence: Cadence | None = None,
) -> list[dict[str, Any]]:
    """
    Tenants due for a Beat enqueue.

    Requires Slack install, active ``agent`` entitlement, schedule enabled,
    a non-empty ``channel_id``, and no successful post yet for the current
    UTC cadence period. Optional ``cadence`` filter (daily vs weekly tick).
    """
    return list_due_recurring_reports(db, cadence=cadence)


__all__ = [
    "DEFAULT_AGENT_NAME",
    "DEFAULT_CADENCE",
    "DEFAULT_ENABLED",
    "SCHEDULE_KEY",
    "Cadence",
    "claim_recurring_report_period",
    "get_recurring_report_schedule",
    "is_recurring_report_enabled",
    "list_tenants_for_scheduled_reports",
    "mark_recurring_report_posted",
    "normalize_cadence",
    "release_recurring_report_period_claim",
    "set_recurring_report_schedule",
    "window_label_for_cadence",
]
