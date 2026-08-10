"""Per-tenant recurring report schedule (channel + cadence + enable).

Persistence: ``ScheduleStore``. Kind rules: ``RecurringReportStrategy``.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.db.models import AgentConfig
from api.app.schedules.kinds import (
    RECURRING_REPORT_KEY,
    Cadence,
    list_due_recurring_reports,
    normalize_cadence,
    window_label_for_cadence,
)
from api.app.schedules.service import patch_kind, read_kind
from api.app.schedules.store import DEFAULT_AGENT_NAME

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


def list_tenants_for_scheduled_reports(
    db: Session,
    *,
    cadence: Cadence | None = None,
) -> list[dict[str, Any]]:
    """
    Tenants due for a Beat enqueue.

    Requires Slack install, active ``agent`` entitlement, schedule enabled,
    and a non-empty ``channel_id``. Optional ``cadence`` filter (daily vs weekly tick).
    """
    return list_due_recurring_reports(db, cadence=cadence)


__all__ = [
    "DEFAULT_AGENT_NAME",
    "DEFAULT_CADENCE",
    "DEFAULT_ENABLED",
    "SCHEDULE_KEY",
    "Cadence",
    "get_recurring_report_schedule",
    "is_recurring_report_enabled",
    "list_tenants_for_scheduled_reports",
    "normalize_cadence",
    "set_recurring_report_schedule",
    "window_label_for_cadence",
]
