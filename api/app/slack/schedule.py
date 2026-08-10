"""Per-tenant Slack history sync schedule (enable/disable for Beat)."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.billing.plans import tenant_has_entitlement
from api.app.db.models import AgentConfig, SlackInstall

SCHEDULE_KEY = "slack_history_sync"
DEFAULT_AGENT_NAME = "default"
# Beat only: missing / unset schedules → enabled (default hourly).
DEFAULT_SYNC_ENABLED = True


def _sync_block(schedules: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not schedules:
        return {}
    block = schedules.get(SCHEDULE_KEY)
    return block if isinstance(block, dict) else {}


def is_slack_history_sync_enabled(db: Session, tenant_id: UUID) -> bool:
    """Return whether periodic Beat should enqueue sync for this tenant."""
    config = db.scalar(
        select(AgentConfig).where(
            AgentConfig.tenant_id == tenant_id,
            AgentConfig.name == DEFAULT_AGENT_NAME,
        )
    )
    if config is None:
        return DEFAULT_SYNC_ENABLED
    block = _sync_block(config.schedules)
    if "enabled" not in block:
        return DEFAULT_SYNC_ENABLED
    return bool(block["enabled"])


def set_slack_history_sync_enabled(
    db: Session,
    *,
    tenant_id: UUID,
    enabled: bool,
) -> AgentConfig:
    """Upsert default agent_config schedules.slack_history_sync.enabled."""
    config = db.scalar(
        select(AgentConfig).where(
            AgentConfig.tenant_id == tenant_id,
            AgentConfig.name == DEFAULT_AGENT_NAME,
        )
    )
    if config is None:
        config = AgentConfig(
            tenant_id=tenant_id,
            name=DEFAULT_AGENT_NAME,
            schedules={SCHEDULE_KEY: {"enabled": enabled}},
        )
        db.add(config)
    else:
        schedules = dict(config.schedules or {})
        block = dict(_sync_block(schedules))
        block["enabled"] = enabled
        schedules[SCHEDULE_KEY] = block
        config.schedules = schedules
        db.add(config)
    db.commit()
    db.refresh(config)
    return config


def list_tenants_for_scheduled_slack_sync(db: Session) -> list[UUID]:
    """
    Tenants that should receive the hourly Beat enqueue.

    Requires a Slack install, active ``sync`` entitlement, and sync not
    explicitly disabled.
    """
    install_tenant_ids = db.scalars(select(SlackInstall.tenant_id).distinct()).all()
    due: list[UUID] = []
    for tenant_id in install_tenant_ids:
        if not tenant_has_entitlement(db, tenant_id, "sync"):
            continue
        if is_slack_history_sync_enabled(db, tenant_id):
            due.append(tenant_id)
    return due
