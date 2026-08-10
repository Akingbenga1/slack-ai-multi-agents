"""Agent dry-run + org agent settings HTTP API."""

from __future__ import annotations

from typing import Annotated, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.app.agent.config_store import (
    agent_settings_dict,
    update_agent_settings,
)
from api.app.auth.deps import require_tenant_access
from api.app.auth.tenant_resolve import resolve_tenant_uuid_for_principal
from api.app.auth.tokens import AuthPrincipal
from api.app.db.session import get_db
from api.app.logging_config import get_logger
from api.app.schedules import patch_schedules, read_all_kinds
from api.app.tenant import get_client_id

logger = get_logger("api.agent.routes")

router = APIRouter(prefix="/agent", tags=["agent"])


class DryRunRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=8000)
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional thread key; defaults to a new UUID per call",
        max_length=200,
    )


class ChunkResponse(BaseModel):
    point_id: str
    score: float
    text: str
    kind: str
    client_id: str
    label: str | None = None
    channel: str | None = None
    filename: str | None = None


class DryRunResponse(BaseModel):
    client_id: str
    thread_id: str
    question: str
    answer: str
    workflow: str
    model_tier: str
    complexity_flags: list[str]
    usage_tokens: int
    hedge: bool
    retrieved_chunks: list[ChunkResponse]


class AllowlistBody(BaseModel):
    channels: list[str] = Field(default_factory=list)


class AgentConfigResponse(BaseModel):
    client_id: str
    config_id: str
    name: str
    system_prompt: Optional[str] = None
    allowlist: Optional[AllowlistBody] = None
    schedules: dict[str, Any]
    updated_at: Optional[str] = None


class AgentConfigUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    system_prompt: Optional[str] = Field(default=None, max_length=20000)
    clear_system_prompt: bool = False
    allowlist: Optional[AllowlistBody] = None
    clear_allowlist: bool = False


class SlackHistorySyncScheduleBody(BaseModel):
    enabled: Optional[bool] = None


class RecurringReportScheduleBody(BaseModel):
    enabled: Optional[bool] = None
    channel_id: Optional[str] = None
    clear_channel: bool = False
    cadence: Optional[str] = Field(default=None, description="daily or weekly")
    window_label: Optional[str] = None


class AgentSchedulesUpdate(BaseModel):
    slack_history_sync: Optional[SlackHistorySyncScheduleBody] = None
    recurring_report: Optional[RecurringReportScheduleBody] = None


class AgentSchedulesResponse(BaseModel):
    client_id: str
    schedules: dict[str, Any]


def _require_client_uuid(principal: AuthPrincipal) -> UUID:
    return resolve_tenant_uuid_for_principal(
        principal,
        missing_detail="tenant context required",
    )


def _to_config_response(payload: dict[str, Any]) -> AgentConfigResponse:
    allow = payload.get("allowlist")
    return AgentConfigResponse(
        client_id=payload["client_id"],
        config_id=payload["config_id"],
        name=payload["name"],
        system_prompt=payload.get("system_prompt"),
        allowlist=AllowlistBody(**allow) if isinstance(allow, dict) else AllowlistBody(),
        schedules=payload.get("schedules") or {},
        updated_at=payload.get("updated_at"),
    )


@router.get("/config", response_model=AgentConfigResponse)
def get_agent_config(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentConfigResponse:
    """Return org agent settings (name, prompt, allowlist, schedule summary)."""
    tid = _require_client_uuid(principal)
    return _to_config_response(agent_settings_dict(db, tid))


@router.patch("/config", response_model=AgentConfigResponse)
def patch_agent_config(
    body: AgentConfigUpdate,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentConfigResponse:
    """Update org agent name / system_prompt / channel allowlist."""
    tid = _require_client_uuid(principal)
    try:
        update_agent_settings(
            db,
            tid,
            name=body.name,
            system_prompt=body.system_prompt,
            clear_system_prompt=body.clear_system_prompt,
            allowlist=(
                body.allowlist.model_dump() if body.allowlist is not None else None
            ),
            clear_allowlist=body.clear_allowlist,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return _to_config_response(agent_settings_dict(db, tid))


@router.get("/schedules", response_model=AgentSchedulesResponse)
def get_agent_schedules(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentSchedulesResponse:
    """Read Strategy-normalized schedule blocks for the tenant."""
    tid = _require_client_uuid(principal)
    return AgentSchedulesResponse(
        client_id=str(tid),
        schedules=read_all_kinds(db, tid),
    )


@router.patch("/schedules", response_model=AgentSchedulesResponse)
def patch_agent_schedules(
    body: AgentSchedulesUpdate,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentSchedulesResponse:
    """
    Unified schedules write path (portal + Beat share Strategy + store).

    Accepts one or both kind patches in a single request.
    """
    tid = _require_client_uuid(principal)
    sync_patch = (
        body.slack_history_sync.model_dump(exclude_unset=True)
        if body.slack_history_sync is not None
        else None
    )
    report_patch = (
        body.recurring_report.model_dump(exclude_unset=True)
        if body.recurring_report is not None
        else None
    )
    try:
        schedules = patch_schedules(
            db,
            tenant_id=tid,
            slack_history_sync=sync_patch,
            recurring_report=report_patch,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return AgentSchedulesResponse(client_id=str(tid), schedules=schedules)


@router.post("/dry-run", response_model=DryRunResponse)
def agent_dry_run(
    body: DryRunRequest,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> DryRunResponse:
    """
    Run LangGraph offline for the caller's tenant (no Slack reply).

    Uses stub LLM when `ANTHROPIC_API_KEY` is unset.
    """
    _ = principal
    _ = db  # session ensures DB is up; usage recorded inside run_agent
    client_id = get_client_id()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tenant context required",
        )
    try:
        UUID(str(client_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant id",
        ) from exc

    from api.app.agent.run import run_agent

    try:
        result = run_agent(
            client_id=str(client_id),
            question=body.question,
            conversation_id=body.conversation_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("agent_dry_run_failed client_id=%s", client_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="agent_run_failed",
        ) from exc

    chunks = [_chunk_response(c) for c in result.get("retrieved_chunks") or []]
    return DryRunResponse(
        client_id=result["client_id"],
        thread_id=result["thread_id"],
        question=result["question"],
        answer=result["answer"],
        workflow=str(result.get("workflow") or "qa"),
        model_tier=str(result.get("model_tier") or "haiku"),
        complexity_flags=list(result.get("complexity_flags") or []),
        usage_tokens=int(result.get("usage_tokens") or 0),
        hedge=bool(result.get("hedge")),
        retrieved_chunks=chunks,
    )


def _chunk_response(raw: dict[str, Any]) -> ChunkResponse:
    return ChunkResponse(
        point_id=str(raw.get("point_id") or ""),
        score=float(raw.get("score") or 0.0),
        text=str(raw.get("text") or ""),
        kind=str(raw.get("kind") or ""),
        client_id=str(raw.get("client_id") or ""),
        label=raw.get("label"),
        channel=raw.get("channel"),
        filename=raw.get("filename"),
    )
