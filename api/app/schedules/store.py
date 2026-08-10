"""Shared ``AgentConfig.schedules`` persistence (Sprint 28.1).

Smell: twin upsert / get-block / list-due loops in ``slack.schedule`` and
``reports.schedule``. Repository-style store owns JSONB block CRUD once;
kind-specific validation lives on ``ScheduleKindStrategy`` (28.2).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db.models import AgentConfig, SlackInstall

DEFAULT_AGENT_NAME = "default"


def _load_default_config(db: Session, tenant_id: UUID) -> AgentConfig | None:
    return db.scalar(
        select(AgentConfig).where(
            AgentConfig.tenant_id == tenant_id,
            AgentConfig.name == DEFAULT_AGENT_NAME,
        )
    )


def get_block(db: Session, tenant_id: UUID, key: str) -> dict[str, Any]:
    """Return a copy of ``schedules[key]`` or ``{}`` when missing/invalid."""
    config = _load_default_config(db, tenant_id)
    if config is None or not config.schedules:
        return {}
    block = config.schedules.get(key)
    return dict(block) if isinstance(block, dict) else {}


def upsert_block(
    db: Session,
    *,
    tenant_id: UUID,
    key: str,
    block: dict[str, Any],
    merge: bool = True,
    commit: bool = True,
) -> AgentConfig:
    """
    Write ``agent_configs.schedules[key]`` on the default agent row.

    When ``merge`` is True, patch onto any existing block; when False, replace
    the key with ``block`` as-is.
    """
    config = _load_default_config(db, tenant_id)
    payload = dict(block)
    if config is None:
        config = AgentConfig(
            tenant_id=tenant_id,
            name=DEFAULT_AGENT_NAME,
            schedules={key: payload},
        )
        db.add(config)
    else:
        schedules = dict(config.schedules or {})
        if merge:
            existing = schedules.get(key)
            base = dict(existing) if isinstance(existing, dict) else {}
            base.update(payload)
            schedules[key] = base
        else:
            schedules[key] = payload
        config.schedules = schedules
        db.add(config)
    if commit:
        db.commit()
        db.refresh(config)
    return config


def list_tenants_for(
    db: Session,
    key: str,
    predicate: Callable[[UUID, dict[str, Any]], bool],
    *,
    candidate_tenant_ids: Iterable[UUID] | None = None,
) -> list[UUID]:
    """
    Tenants whose schedule block for ``key`` passes ``predicate``.

    Default candidates: distinct ``SlackInstall.tenant_id`` (Beat jobs need Slack).
    """
    if candidate_tenant_ids is None:
        ids = list(db.scalars(select(SlackInstall.tenant_id).distinct()).all())
    else:
        ids = list(candidate_tenant_ids)
    due: list[UUID] = []
    for tenant_id in ids:
        block = get_block(db, tenant_id, key)
        if predicate(tenant_id, block):
            due.append(tenant_id)
    return due


__all__ = [
    "DEFAULT_AGENT_NAME",
    "get_block",
    "list_tenants_for",
    "upsert_block",
]
