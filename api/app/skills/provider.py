"""Pluggable skill provider for Deep Agents (progressive disclosure)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from api.app.blob_store import BlobStore
from api.app.settings import Settings, get_settings
from api.app.skills.store import SkillsStore, SkillsStoreError


class SkillProvider(Protocol):
    """Boundary Deep Agents use to list and load tenant skills."""

    def list_index(self) -> list[dict[str, str]]:
        """Short catalog index: name, description, path."""
        ...

    def load_markdown(self, path: str) -> str:
        """Load full skill .md after selection."""
        ...


@dataclass
class SkillUsageEvent:
    path: str
    action: str
    ok: bool
    detail: str | None = None


@dataclass
class TenantSkillRuntime:
    tools: list[Any] = field(default_factory=list)
    usage: list[SkillUsageEvent] = field(default_factory=list)
    index: list[dict[str, str]] = field(default_factory=list)


class BlobSkillProvider:
    """SkillProvider backed by SkillsStore / BlobStore."""

    def __init__(self, store: SkillsStore) -> None:
        self._store = store

    def list_index(self) -> list[dict[str, str]]:
        return self._store.list_index()

    def load_markdown(self, path: str) -> str:
        return self._store.read_skill(path).content


def build_skill_provider(
    *,
    client_id: str,
    settings: Settings | None = None,
    blob_store: BlobStore | None = None,
    provider: SkillProvider | None = None,
) -> SkillProvider:
    if provider is not None:
        return provider
    store = SkillsStore(
        client_id=client_id,
        blob_store=blob_store,
        settings=settings or get_settings(),
    )
    return BlobSkillProvider(store)


def build_tenant_skill_runtime(
    *,
    client_id: str,
    run_key: str,
    settings: Settings | None = None,
    blob_store: BlobStore | None = None,
    provider: SkillProvider | None = None,
) -> TenantSkillRuntime:
    """Build list_tenant_skills + load_tenant_skill tools for the harness."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    skill_provider = build_skill_provider(
        client_id=client_id,
        settings=settings,
        blob_store=blob_store,
        provider=provider,
    )
    runtime = TenantSkillRuntime(index=list(skill_provider.list_index()))

    class _Empty(BaseModel):
        pass

    class _LoadArgs(BaseModel):
        path: str = Field(description="Skill path from the catalog index (ends with .md)")

    def _list_skills() -> str:
        import json

        try:
            index = skill_provider.list_index()
            runtime.index = list(index)
            runtime.usage.append(
                SkillUsageEvent(path="", action="list_index", ok=True)
            )
            return json.dumps({"skills": index}, indent=2)
        except Exception as exc:
            runtime.usage.append(
                SkillUsageEvent(
                    path="",
                    action="list_index",
                    ok=False,
                    detail=str(exc),
                )
            )
            return json.dumps({"skills": [], "error": str(exc)})

    def _load_skill(path: str) -> str:
        rel = (path or "").strip()
        try:
            content = skill_provider.load_markdown(rel)
            runtime.usage.append(
                SkillUsageEvent(path=rel, action="load", ok=True)
            )
            return content
        except SkillsStoreError as exc:
            runtime.usage.append(
                SkillUsageEvent(
                    path=rel,
                    action="load",
                    ok=False,
                    detail=str(exc),
                )
            )
            return f"Error: {exc}"
        except Exception as exc:
            runtime.usage.append(
                SkillUsageEvent(
                    path=rel,
                    action="load",
                    ok=False,
                    detail=str(exc),
                )
            )
            return f"Error loading skill: {exc}"

    runtime.tools = [
        StructuredTool.from_function(
            func=_list_skills,
            name="list_tenant_skills",
            description=(
                "List this tenant's skills (name, description, path only). "
                "Use progressive disclosure: call this first, then load_tenant_skill "
                "for the one skill you need."
            ),
            args_schema=_Empty,
        ),
        StructuredTool.from_function(
            func=_load_skill,
            name="load_tenant_skill",
            description=(
                "Load the full markdown body of one tenant skill by path "
                "from list_tenant_skills. Do not load every skill."
            ),
            args_schema=_LoadArgs,
        ),
    ]
    _ = run_key  # reserved for future per-run tracing
    return runtime


def usage_as_dicts(events: list[SkillUsageEvent]) -> list[dict[str, Any]]:
    return [
        {
            "path": e.path,
            "action": e.action,
            "ok": e.ok,
            "detail": e.detail,
        }
        for e in events
    ]
