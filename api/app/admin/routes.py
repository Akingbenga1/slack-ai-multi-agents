"""Platform admin HTTP routes (Sprint 21)."""

from __future__ import annotations

from typing import Annotated, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.app.admin.actions import (
    list_audit_logs,
    override_tenant_budgets,
    override_tenant_plan,
    set_tenant_status,
)
from api.app.admin.health_overview import platform_health_overview
from api.app.admin.provision import OrganisationError, create_organisation
from api.app.admin.tenants import get_tenant_detail, list_tenant_summaries, tenant_summary_row
from api.app.auth.deps import require_platform_owner
from api.app.auth.tokens import AuthPrincipal
from api.app.db.session import get_db
from api.app.settings import Settings, get_settings
from api.app.tenant import set_client_id

router = APIRouter(prefix="/admin", tags=["admin"])


class CreateTenantBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=64)
    admin_email: str = Field(min_length=3, max_length=320)
    admin_password: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="Optional; generated when omitted (returned once)",
    )
    admin_display_name: Optional[str] = Field(default=None, max_length=255)
    activate_plan: bool = Field(
        default=False,
        description="Local demo: set plan active without Stripe Checkout",
    )


class TenantStatusBody(BaseModel):
    status: str = Field(description="active | suspended")


class BudgetOverrideBody(BaseModel):
    tokens_daily: Optional[int] = None
    tokens_monthly: Optional[int] = None
    jobs_daily: Optional[int] = None


class TenantPlanBody(BaseModel):
    plan_status: str = Field(description="active | inactive")
    reason: str = Field(min_length=1, max_length=512, description="Operator reason for audit trail")


def _audit_row(row: Any) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
        "actor_email": row.actor_email,
        "action": row.action,
        "tenant_id": str(row.tenant_id) if row.tenant_id else None,
        "detail": row.detail or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/tenants")
def admin_list_tenants(
    _: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """PO-01 / PO-25 — tenant list with plan, Slack, last sync."""
    items = list_tenant_summaries(db)
    return {"tenants": items, "count": len(items)}


@router.post("/tenants", status_code=status.HTTP_201_CREATED)
def admin_create_tenant(
    body: CreateTenantBody,
    principal: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """PO-04 — stand up a second (or Nth) org via admin portal."""
    try:
        created = create_organisation(
            db,
            name=body.name,
            slug=body.slug,
            admin_email=body.admin_email,
            admin_password=body.admin_password,
            admin_display_name=body.admin_display_name,
            activate_plan=body.activate_plan,
            actor_user_id=principal.sub,
            actor_email=principal.email,
            settings=settings,
        )
    except OrganisationError as exc:
        msg = str(exc)
        code = (
            status.HTTP_409_CONFLICT
            if "already exists" in msg
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=msg) from exc

    set_client_id(str(created.tenant.id))
    summary = tenant_summary_row(db, created.tenant)
    payload: dict[str, Any] = {
        "tenant": summary,
        "admin": {
            "id": str(created.admin.id),
            "email": created.admin.email,
            "display_name": created.admin.display_name,
        },
        "created": created.created,
    }
    if created.admin_password:
        payload["admin_password"] = created.admin_password
        payload["note"] = "Store admin_password now; it is not shown again."
    return payload


@router.get("/tenants/{tenant_id}")
def admin_get_tenant(
    tenant_id: UUID,
    _: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    set_client_id(str(tenant_id))
    detail = get_tenant_detail(db, tenant_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return detail


@router.get("/health")
def admin_platform_health(
    _: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
) -> dict[str, Any]:
    """PO-13 — Compose deep health + recent job failure / usage rates."""
    return platform_health_overview(db, settings, hours=hours)


@router.patch("/tenants/{tenant_id}/status")
def admin_set_tenant_status(
    tenant_id: UUID,
    body: TenantStatusBody,
    principal: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    set_client_id(str(tenant_id))
    try:
        tenant = set_tenant_status(
            db,
            tenant_id,
            status=body.status,
            actor_user_id=principal.sub,
            actor_email=principal.email,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"id": str(tenant.id), "status": tenant.status}


@router.patch("/tenants/{tenant_id}/budgets")
def admin_override_budgets(
    tenant_id: UUID,
    body: BudgetOverrideBody,
    principal: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    set_client_id(str(tenant_id))
    payload = body.model_dump(exclude_none=True)
    try:
        row = override_tenant_budgets(
            db,
            tenant_id,
            budgets=payload,
            actor_user_id=principal.sub,
            actor_email=principal.email,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "tenant_id": str(row.tenant_id),
        "plan_status": row.plan_status,
        "plan_source": row.plan_source,
        "override_reason": row.override_reason,
        "entitlements": row.entitlements or {},
    }


@router.patch("/tenants/{tenant_id}/plan")
def admin_override_tenant_plan(
    tenant_id: UUID,
    body: TenantPlanBody,
    principal: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """PO-01 / PO-25 — activate/deactivate plan without Stripe (post-create waiver)."""
    set_client_id(str(tenant_id))
    try:
        row = override_tenant_plan(
            db,
            tenant_id,
            plan_status=body.plan_status,
            reason=body.reason,
            actor_user_id=principal.sub,
            actor_email=principal.email,
            settings=settings,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "tenant_id": str(row.tenant_id),
        "plan_status": row.plan_status,
        "plan_source": row.plan_source,
        "override_reason": row.override_reason,
        "entitlements": row.entitlements or {},
    }


@router.get("/audit-logs")
def admin_list_audit_logs(
    _: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
    tenant_id: Annotated[Optional[UUID], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    rows = list_audit_logs(db, tenant_id=tenant_id, limit=limit)
    return {"logs": [_audit_row(r) for r in rows], "count": len(rows)}


class AgentTraceBody(BaseModel):
    tenant_id: UUID = Field(description="Tenant to plan and execute against")
    question: str = Field(..., min_length=1, max_length=8000)


def _llm_runtime_info(settings: Settings) -> dict[str, Any]:
    from api.app.agent.llm_config import ADAPTER_SHAPE_STUB, resolve_llm_runtime_config

    try:
        config = resolve_llm_runtime_config(settings)
    except ValueError:
        provider = (settings.llm_provider or "anthropic").strip().lower()
        return {
            "llm_provider": provider,
            "orchestrator_model_tier": "capable",
            "orchestrator_model": "unknown",
            "executor_model_tier": "fast",
            "executor_model": "unknown",
        }
    if config.adapter_shape == ADAPTER_SHAPE_STUB:
        capable = "stub-capable"
        fast = "stub-fast"
    else:
        capable = config.model_capable
        fast = config.model_fast
    return {
        "llm_provider": config.provider_id,
        "orchestrator_model_tier": "capable",
        "orchestrator_model": capable,
        "executor_model_tier": "fast",
        "executor_model": fast,
    }


@router.post("/agent-trace")
def admin_agent_trace(
    body: AgentTraceBody,
    _: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Platform-owner only: run plan→execute and return prompts, steps, answer."""
    from api.app.agent.facade import plan_and_execute
    from api.app.db.plan_store import list_agent_plan_steps
    from api.app.db.session import SessionLocal
    from api.app.tenant import set_client_id

    tenant_id = str(body.tenant_id)
    set_client_id(tenant_id)
    detail = get_tenant_detail(db, body.tenant_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="tenant not found",
        )

    try:
        result = plan_and_execute(
            client_id=tenant_id,
            question=body.question,
            extra={
                "db_factory": SessionLocal,
                "include_trace": True,
                "settings": settings,
            },
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"agent_run_failed: {exc}",
        ) from exc

    plan_id = result.extra.get("plan_id")
    executed_steps: list[dict[str, Any]] = []
    if plan_id:
        # Fresh session: plan/execute commits on its own SessionLocal handles.
        with SessionLocal() as step_db:
            for step in list_agent_plan_steps(
                step_db, tenant_id=tenant_id, plan_id=plan_id
            ):
                executed_steps.append(
                    {
                        "step_index": step.step_index,
                        "tool_name": step.tool_name,
                        "arguments": step.arguments,
                        "success_criteria": step.success_criteria,
                        "status": step.status,
                        "result": step.result,
                        "error": step.error,
                    }
                )

    llm = _llm_runtime_info(settings)
    return {
        "tenant_id": tenant_id,
        "tenant_name": detail.get("name"),
        "question": body.question,
        "status": result.status,
        "phase": result.extra.get("phase"),
        "workflow": result.extra.get("workflow") or "qa",
        "plan_id": plan_id,
        "run_id": result.extra.get("run_id"),
        "orchestrator_system_prompt": result.extra.get(
            "orchestrator_system_prompt"
        ),
        "orchestrator_user_prompt": result.extra.get(
            "orchestrator_user_prompt"
        ),
        "plan_steps": result.extra.get("plan_steps") or [],
        "executed_steps": executed_steps,
        "planner_model": result.extra.get("planner_model")
        or llm["orchestrator_model"],
        "final_answer": result.message,
        "llm": llm,
    }
