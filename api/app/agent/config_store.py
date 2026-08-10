"""Tenant agent_config read/update (Sprint 19.1)."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db.models import AgentConfig
from api.app.schedules import DEFAULT_AGENT_NAME, read_all_kinds

# Row key stays ``name="default"`` (schedule lookups). Display name lives in
# ``extra.display_name``. Allowlist: ``{"channels": ["C123", ...]}``.


def normalize_allowlist(raw: Any) -> dict[str, Any] | None:
    """Normalize allowlist to ``{"channels": [...]}`` or None."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        channels = raw.get("channels")
        if channels is None and "channel_ids" in raw:
            channels = raw.get("channel_ids")
        if channels is None:
            return {"channels": []} if raw == {} else dict(raw)
        if not isinstance(channels, list):
            raise ValueError("allowlist.channels must be a list of channel ids")
        cleaned = [str(c).strip() for c in channels if str(c).strip()]
        return {"channels": cleaned}
    raise ValueError("allowlist must be an object with optional channels[]")


def _display_name(config: AgentConfig) -> str:
    extra = config.extra if isinstance(config.extra, dict) else {}
    label = str(extra.get("display_name") or "").strip()
    if label:
        return label
    # Fallback: never expose internal key as the product name if still default
    if config.name and config.name != DEFAULT_AGENT_NAME:
        return config.name
    return "Workspace agent"


def get_or_create_default_config(db: Session, tenant_id: UUID) -> AgentConfig:
    config = db.scalar(
        select(AgentConfig).where(
            AgentConfig.tenant_id == tenant_id,
            AgentConfig.name == DEFAULT_AGENT_NAME,
        )
    )
    if config is not None:
        return config
    config = AgentConfig(
        tenant_id=tenant_id,
        name=DEFAULT_AGENT_NAME,
        system_prompt=None,
        allowlist=None,
        schedules=None,
        extra={"display_name": "Workspace agent"},
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def agent_settings_dict(db: Session, tenant_id: UUID) -> dict[str, Any]:
    """Public settings payload for GET /agent/config."""
    config = get_or_create_default_config(db, tenant_id)
    allowlist = normalize_allowlist(config.allowlist) if config.allowlist else {
        "channels": []
    }
    return {
        "client_id": str(tenant_id),
        "config_id": str(config.id),
        "name": _display_name(config),
        "system_prompt": config.system_prompt,
        "allowlist": allowlist,
        "schedules": read_all_kinds(db, tenant_id),
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


def update_agent_settings(
    db: Session,
    tenant_id: UUID,
    *,
    name: str | None = None,
    system_prompt: str | None = None,
    clear_system_prompt: bool = False,
    allowlist: dict[str, Any] | None = None,
    clear_allowlist: bool = False,
) -> AgentConfig:
    """
    Update display name / prompt / allowlist on the default agent_config.

    Schedule enable/disable stays on ``PATCH /agent/schedules`` (legacy
    ``/jobs/.../schedule`` adapters remain). Internal row ``name`` remains
    ``default``.
    """
    config = get_or_create_default_config(db, tenant_id)
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("name must be non-empty")
        if len(cleaned) > 255:
            raise ValueError("name must be at most 255 characters")
        extra = dict(config.extra or {})
        extra["display_name"] = cleaned
        config.extra = extra
    if clear_system_prompt:
        config.system_prompt = None
    elif system_prompt is not None:
        text = system_prompt.strip()
        config.system_prompt = text or None
    if clear_allowlist:
        config.allowlist = {"channels": []}
    elif allowlist is not None:
        config.allowlist = normalize_allowlist(allowlist)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def load_org_system_prompt(db: Session, tenant_id: UUID | str) -> Optional[str]:
    """Return stored org system_prompt if set (for compose overlay)."""
    tid = UUID(str(tenant_id))
    config = db.scalar(
        select(AgentConfig).where(
            AgentConfig.tenant_id == tid,
            AgentConfig.name == DEFAULT_AGENT_NAME,
        )
    )
    if config is None:
        return None
    text = (config.system_prompt or "").strip()
    return text or None


__all__ = [
    "agent_settings_dict",
    "get_or_create_default_config",
    "load_org_system_prompt",
    "normalize_allowlist",
    "update_agent_settings",
]
