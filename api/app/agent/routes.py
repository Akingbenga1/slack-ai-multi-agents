"""Agent dry-run + org agent settings HTTP API."""

from __future__ import annotations

from typing import Annotated, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
from api.app.logging_config import get_logger, log_dry_run_activity
from api.app.schedules import patch_schedules, read_all_kinds
from api.app.settings import get_settings

logger = get_logger("api.agent.routes")

router = APIRouter(prefix="/agent", tags=["agent"])

_MAX_DRY_RUN_UPLOAD_BYTES = 50 * 1024 * 1024


class DryRunRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=8000)
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional thread key; defaults to a new UUID per call",
        max_length=200,
    )
    include_trace: bool = Field(
        default=False,
        description="When true, return orchestrator prompts (Tool RAG shortlist proof).",
    )
    upload_id: Optional[str] = Field(
        default=None,
        description="Existing tenant upload id ({upload_id}_filename under UPLOAD_DIR).",
        max_length=80,
    )
    storage_relative_path: Optional[str] = Field(
        default=None,
        description="Existing blob key (tenant-scoped) to attach for this dry-run.",
        max_length=500,
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


class DryRunAttachmentInfo(BaseModel):
    filename: str
    upload_id: str | None = None
    storage_relative_path: str
    local_path: str | None = None


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
    plan_id: str | None = None
    status: str | None = None
    orchestrator_user_prompt: str | None = None
    plan_steps: list[dict[str, Any]] | None = None
    attachment: DryRunAttachmentInfo | None = None


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
async def agent_dry_run(
    request: Request,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> DryRunResponse:
    """
    Run orchestrator → executor offline for the caller's tenant (no Slack reply).

    JSON body: ``DryRunRequest`` (optional ``upload_id`` / ``storage_relative_path``).
    Multipart: form fields ``question``, optional ``conversation_id``,
    ``include_trace``, ``upload_id``, ``storage_relative_path``, and optional
    ``file`` (stored via BlobStore, not ingested to RAG).

    When a file is provided, attachments (filename, storage_relative_path,
    local_path) are passed into ``plan_and_execute`` for the planner/executor.
    """
    _ = db
    from api.app.agent.dry_run_files import (
        attachment_from_storage_relative_path,
        attachment_from_upload_bytes,
        attachment_from_upload_id,
    )
    from api.app.db.session import SessionLocal

    client_id = resolve_tenant_uuid_for_principal(principal)
    cid = str(client_id)
    settings = get_settings()

    try:
        question, conversation_id, include_trace, attachment = (
            await _parse_dry_run_input(
                request,
                client_id=cid,
                settings=settings,
                attachment_from_upload_bytes=attachment_from_upload_bytes,
                attachment_from_upload_id=attachment_from_upload_id,
                attachment_from_storage_relative_path=attachment_from_storage_relative_path,
            )
        )
    except ValueError as exc:
        log_dry_run_activity(
            endpoint="POST /agent/dry-run",
            phase="error",
            client_id=cid,
            request={},
            error={"status_code": 400, "detail": str(exc)},
            celery=None,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    request_payload: dict[str, Any] = {
        "question": question,
        "conversation_id": conversation_id,
        "include_trace": include_trace,
    }
    if attachment:
        request_payload["attachment"] = {
            "filename": attachment.get("filename"),
            "upload_id": attachment.get("upload_id"),
            "storage_relative_path": attachment.get("storage_relative_path"),
            "local_path": attachment.get("local_path"),
        }

    log_dry_run_activity(
        endpoint="POST /agent/dry-run",
        phase="request",
        client_id=cid,
        request=request_payload,
        celery=None,
    )
    from api.app.agent.facade import plan_and_execute

    attachments = [attachment] if attachment else []
    try:
        result = plan_and_execute(
            client_id=cid,
            question=question,
            conversation_id=conversation_id,
            attachments=attachments,
            extra={
                "db_factory": SessionLocal,
                "include_trace": bool(include_trace),
            },
        )
    except ValueError as exc:
        log_dry_run_activity(
            endpoint="POST /agent/dry-run",
            phase="error",
            client_id=cid,
            request=request_payload,
            error={"status_code": 400, "detail": str(exc)},
            celery=None,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("agent_dry_run_failed client_id=%s", client_id)
        log_dry_run_activity(
            endpoint="POST /agent/dry-run",
            phase="error",
            client_id=cid,
            request=request_payload,
            error={"status_code": 502, "detail": "agent_run_failed", "exc": str(exc)},
            celery=None,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="agent_run_failed",
        ) from exc

    workflow = result.extra.get("workflow") or "qa"
    plan_id = result.extra.get("plan_id")
    attachment_info = None
    if attachment:
        attachment_info = DryRunAttachmentInfo(
            filename=str(attachment.get("filename") or ""),
            upload_id=(
                str(attachment["upload_id"])
                if attachment.get("upload_id")
                else None
            ),
            storage_relative_path=str(
                attachment.get("storage_relative_path") or ""
            ),
            local_path=(
                str(attachment["local_path"])
                if attachment.get("local_path")
                else None
            ),
        )
    response = DryRunResponse(
        client_id=result.client_id,
        thread_id=str(plan_id or ""),
        question=question,
        answer=result.message,
        workflow=str(workflow),
        model_tier="capable",
        complexity_flags=[],
        usage_tokens=0,
        hedge=result.status != "succeeded",
        retrieved_chunks=[],
        plan_id=str(plan_id) if plan_id else None,
        status=result.status,
        orchestrator_user_prompt=(
            (str(result.extra.get("orchestrator_user_prompt") or "") or None)
            if include_trace
            else None
        ),
        plan_steps=(
            list(result.extra.get("plan_steps") or [])
            if include_trace
            else None
        ),
        attachment=attachment_info,
    )
    log_dry_run_activity(
        endpoint="POST /agent/dry-run",
        phase="response",
        client_id=cid,
        request=request_payload,
        response=response.model_dump(),
        celery=None,
    )
    return response


async def _parse_dry_run_input(
    request: Request,
    *,
    client_id: str,
    settings: Any,
    attachment_from_upload_bytes: Any,
    attachment_from_upload_id: Any,
    attachment_from_storage_relative_path: Any,
) -> tuple[str, str | None, bool, dict[str, Any] | None]:
    """Parse JSON or multipart dry-run input; return question + optional attachment."""
    content_type = (request.headers.get("content-type") or "").lower()
    attachment: dict[str, Any] | None = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        question = str(form.get("question") or "").strip()
        if not question:
            raise ValueError("question is required")
        if len(question) > 8000:
            raise ValueError("question exceeds max length 8000")
        conversation_id = form.get("conversation_id")
        conversation_id = (
            str(conversation_id).strip() if conversation_id not in (None, "") else None
        )
        include_raw = str(form.get("include_trace") or "false").strip().lower()
        include_trace = include_raw in {"1", "true", "yes", "on"}
        upload_id = form.get("upload_id")
        upload_id = str(upload_id).strip() if upload_id not in (None, "") else None
        storage_rel = form.get("storage_relative_path")
        storage_rel = (
            str(storage_rel).strip() if storage_rel not in (None, "") else None
        )
        upload = form.get("file")
        has_file = upload is not None and hasattr(upload, "read")
        if has_file and (upload_id or storage_rel):
            raise ValueError(
                "provide only one of file, upload_id, or storage_relative_path"
            )
        if has_file:
            data = await upload.read()  # type: ignore[union-attr]
            if not data:
                raise ValueError("empty file")
            if len(data) > _MAX_DRY_RUN_UPLOAD_BYTES:
                raise ValueError("file too large")
            attachment = attachment_from_upload_bytes(
                client_id=client_id,
                filename=getattr(upload, "filename", None) or "upload.bin",
                data=data,
                content_type=getattr(upload, "content_type", None),
                settings=settings,
            )
        elif upload_id:
            attachment = attachment_from_upload_id(
                client_id=client_id,
                upload_id=upload_id,
                settings=settings,
            )
        elif storage_rel:
            attachment = attachment_from_storage_relative_path(
                client_id=client_id,
                storage_relative_path=storage_rel,
                settings=settings,
            )
        return question, conversation_id, include_trace, attachment

    raw = await request.json()
    body = DryRunRequest.model_validate(raw)
    sources = [
        bool(body.upload_id),
        bool(body.storage_relative_path),
    ]
    if sum(1 for s in sources if s) > 1:
        raise ValueError(
            "provide only one of upload_id or storage_relative_path"
        )
    if body.upload_id:
        attachment = attachment_from_upload_id(
            client_id=client_id,
            upload_id=body.upload_id.strip(),
            settings=settings,
        )
    elif body.storage_relative_path:
        attachment = attachment_from_storage_relative_path(
            client_id=client_id,
            storage_relative_path=body.storage_relative_path.strip(),
            settings=settings,
        )
    return body.question, body.conversation_id, bool(body.include_trace), attachment


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
