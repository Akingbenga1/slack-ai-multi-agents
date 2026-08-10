"""Per-tenant recurring report schedule (channel + cadence + enable)."""

from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.billing.plans import tenant_has_entitlement
from api.app.db.models import AgentConfig, SlackInstall

SCHEDULE_KEY = "recurring_report"
DEFAULT_AGENT_NAME = "default"
DEFAULT_ENABLED = False
DEFAULT_CADENCE: Literal["daily", "weekly"] = "weekly"
Cadence = Literal["daily", "weekly"]

_CADENCE_WINDOWS: dict[str, str] = {
    "daily": "last 24 hours",
    "weekly": "last 7 days",
}


def _report_block(schedules: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not schedules:
        return {}
    block = schedules.get(SCHEDULE_KEY)
    return block if isinstance(block, dict) else {}


def normalize_cadence(value: str | None) -> Cadence:
    raw = (value or DEFAULT_CADENCE).strip().lower()
    if raw not in ("daily", "weekly"):
        raise ValueError("cadence must be 'daily' or 'weekly'")
    return raw  # type: ignore[return-value]


def window_label_for_cadence(cadence: str | None) -> str:
    """Default digest window label for a cadence."""
    key = normalize_cadence(cadence)
    return _CADENCE_WINDOWS[key]


def get_recurring_report_schedule(db: Session, tenant_id: UUID) -> dict[str, Any]:
    """
    Return normalized schedule fields for the tenant.

    Defaults: enabled=False, cadence=weekly, channel_id=None,
    window_label derived from cadence.
    """
    config = db.scalar(
        select(AgentConfig).where(
            AgentConfig.tenant_id == tenant_id,
            AgentConfig.name == DEFAULT_AGENT_NAME,
        )
    )
    block = _report_block(config.schedules if config else None)
    enabled = (
        bool(block["enabled"]) if "enabled" in block else DEFAULT_ENABLED
    )
    cadence = normalize_cadence(
        str(block.get("cadence") or DEFAULT_CADENCE)
        if block.get("cadence") is not None
        else DEFAULT_CADENCE
    )
    channel_id = block.get("channel_id")
    channel = str(channel_id).strip() if channel_id else None
    if channel == "":
        channel = None
    window = str(block.get("window_label") or "").strip() or window_label_for_cadence(
        cadence
    )
    return {
        "enabled": enabled,
        "channel_id": channel,
        "cadence": cadence,
        "window_label": window,
    }


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
    config = db.scalar(
        select(AgentConfig).where(
            AgentConfig.tenant_id == tenant_id,
            AgentConfig.name == DEFAULT_AGENT_NAME,
        )
    )
    if config is None:
        block: dict[str, Any] = {
            "enabled": DEFAULT_ENABLED,
            "cadence": DEFAULT_CADENCE,
            "channel_id": None,
            "window_label": window_label_for_cadence(DEFAULT_CADENCE),
        }
        config = AgentConfig(
            tenant_id=tenant_id,
            name=DEFAULT_AGENT_NAME,
            schedules={SCHEDULE_KEY: block},
        )
        db.add(config)
    else:
        schedules = dict(config.schedules or {})
        block = dict(_report_block(schedules))
        if "enabled" not in block:
            block["enabled"] = DEFAULT_ENABLED
        if "cadence" not in block:
            block["cadence"] = DEFAULT_CADENCE
        if "channel_id" not in block:
            block["channel_id"] = None
        if "window_label" not in block:
            block["window_label"] = window_label_for_cadence(
                str(block.get("cadence") or DEFAULT_CADENCE)
            )
        schedules[SCHEDULE_KEY] = block
        config.schedules = schedules
        db.add(config)

    schedules = dict(config.schedules or {})
    block = dict(_report_block(schedules))

    if enabled is not None:
        block["enabled"] = bool(enabled)
    if clear_channel:
        block["channel_id"] = None
    elif channel_id is not None:
        cleaned = channel_id.strip()
        block["channel_id"] = cleaned or None
    if cadence is not None:
        block["cadence"] = normalize_cadence(cadence)
        # Refresh default window when cadence changes unless explicitly set
        if window_label is None:
            block["window_label"] = window_label_for_cadence(block["cadence"])
    if window_label is not None:
        label = window_label.strip()
        block["window_label"] = label or window_label_for_cadence(
            str(block.get("cadence") or DEFAULT_CADENCE)
        )

    schedules[SCHEDULE_KEY] = block
    config.schedules = schedules
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def list_tenants_for_scheduled_reports(
    db: Session,
    *,
    cadence: Cadence | None = None,
) -> list[dict[str, Any]]:
    """
    Tenants due for a Beat report enqueue.

    Requires Slack install, active ``agent`` entitlement, schedule enabled,
    and a non-empty ``channel_id``. Optional ``cadence`` filter (daily vs weekly tick).
    """
    install_tenant_ids = db.scalars(select(SlackInstall.tenant_id).distinct()).all()
    due: list[dict[str, Any]] = []
    for tenant_id in install_tenant_ids:
        if not tenant_has_entitlement(db, tenant_id, "agent"):
            continue
        sched = get_recurring_report_schedule(db, tenant_id)
        if not sched["enabled"]:
            continue
        if not sched["channel_id"]:
            continue
        if cadence is not None and sched["cadence"] != cadence:
            continue
        due.append(
            {
                "tenant_id": tenant_id,
                "channel_id": sched["channel_id"],
                "cadence": sched["cadence"],
                "window_label": sched["window_label"],
            }
        )
    return due


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
