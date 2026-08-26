"""Control-plane API: list / check / install host CLI tools from tool_registry.

Separate from the executor. Orchestrator never calls these routes.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.app.agent.cli_host import (
    CliHostError,
    check_cli_installed,
    command_from_config,
    has_install_spec,
    host_platform,
    install_cli_tool,
    package_from_config,
)
from api.app.auth.deps import require_tenant_access
from api.app.auth.tenant_resolve import resolve_tenant_uuid_for_principal
from api.app.auth.tokens import AuthPrincipal
from api.app.db.session import get_db
from api.app.db.tool_store import get_tool_registry, list_tool_registry, update_tool_registry
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings

logger = get_logger("api.agent.cli_host_routes")

# Prefix is intentionally NOT under /tools/{tool_name} — that catch-all would
# treat "cli-host" as a tool name and return 404.
router = APIRouter(prefix="/cli-host", tags=["cli-host"])


class CliHostToolRow(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    command: Optional[str] = None
    package: Optional[str] = None
    install: Optional[str] = None
    has_install_spec: bool = False
    created_at: Optional[str] = None


class CliHostInstallSpecUpdate(BaseModel):
    """Merge package / install command into an existing CLI tool config."""

    package: Optional[str] = Field(
        default=None,
        description="Package id for default installers; empty string clears.",
    )
    install: Optional[str] = Field(
        default=None,
        description="Install argv as a shell-like string; empty string clears.",
    )


class CliHostListResponse(BaseModel):
    tools: list[CliHostToolRow]
    platform: str
    install_enabled: bool


class CliHostCheckResponse(BaseModel):
    tool_name: str
    command: str
    installed: bool
    resolved_path: Optional[str] = None
    platform: str


class CliHostInstallResponse(BaseModel):
    tool_name: str
    command: str
    ok: bool
    installed: bool
    install_cmd: list[str] = Field(default_factory=list)
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    resolved_path: Optional[str] = None
    platform: str
    error: Optional[str] = None


def _require_client_uuid(principal: AuthPrincipal):
    return resolve_tenant_uuid_for_principal(
        principal, missing_detail="tenant context required",
    )


def _cli_row_or_404(db: Session, *, tenant_id: str, tool_name: str) -> Any:
    row = get_tool_registry(db, tenant_id=tenant_id, name=tool_name)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tool not found")
    if row.kind != "cli":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"tool {tool_name!r} is kind={row.kind!r}, not cli",
        )
    return row


def _config(row: Any) -> dict[str, Any] | None:
    return row.config if isinstance(row.config, dict) else None


def _install_spec_text(cfg: dict[str, Any] | None) -> str | None:
    """Serialize stored install / install_command for the editor."""
    if not isinstance(cfg, dict):
        return None
    install = cfg.get("install")
    if isinstance(install, list) and install:
        return " ".join(str(x) for x in install)
    if isinstance(install, str) and install.strip():
        return install.strip()
    if isinstance(install, dict):
        plat = host_platform()
        keys = [plat]
        if plat == "windows":
            keys.extend(["win", "win32"])
        elif plat == "darwin":
            keys.extend(["macos", "osx", "mac"])
        elif plat == "linux":
            keys.append("unix")
        for key in keys:
            raw = install.get(key)
            if isinstance(raw, list) and raw:
                return " ".join(str(x) for x in raw)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    raw_cmd = cfg.get("install_command")
    if isinstance(raw_cmd, list) and raw_cmd:
        return " ".join(str(x) for x in raw_cmd)
    if isinstance(raw_cmd, str) and raw_cmd.strip():
        return raw_cmd.strip()
    return None


def _merge_install_spec(
    cfg: dict[str, Any] | None,
    *,
    package: str | None,
    install: str | None,
) -> dict[str, Any]:
    merged = dict(cfg) if isinstance(cfg, dict) else {}
    if package is not None:
        pkg = package.strip()
        if pkg:
            merged["package"] = pkg
        else:
            merged.pop("package", None)
    if install is not None:
        text = install.strip()
        if text:
            merged["install"] = text
            merged.pop("install_command", None)
        else:
            merged.pop("install", None)
            merged.pop("install_command", None)
    return merged


@router.get("", response_model=CliHostListResponse)
def list_cli_host_tools(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CliHostListResponse:
    """List registered CLI tools for the tenant (host readiness control plane)."""
    tid = _require_client_uuid(principal)
    rows = list_tool_registry(db, tenant_id=str(tid))
    tools: list[CliHostToolRow] = []
    for row in rows:
        if row.kind != "cli":
            continue
        cfg = _config(row)
        command: str | None = None
        package: str | None = None
        try:
            command = command_from_config(cfg)
            if isinstance(cfg, dict):
                try:
                    package = package_from_config(cfg, command=command or "")
                except CliHostError:
                    package = str(cfg.get("package") or "").strip() or None
        except CliHostError:
            command = None
        tools.append(
            CliHostToolRow(
                id=str(row.id),
                name=row.name,
                description=row.description,
                command=command,
                package=package,
                install=_install_spec_text(cfg),
                has_install_spec=has_install_spec(cfg),
                created_at=str(row.created_at) if row.created_at else None,
            )
        )
    tools.sort(key=lambda t: t.name.lower())
    return CliHostListResponse(
        tools=tools,
        platform=host_platform(),
        install_enabled=bool(settings.cli_host_install_enabled),
    )


@router.post("/{tool_name}/check", response_model=CliHostCheckResponse)
def check_cli_host_tool(
    tool_name: str,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> CliHostCheckResponse:
    """Check whether a registered CLI tool's command is on the host PATH."""
    tid = _require_client_uuid(principal)
    row = _cli_row_or_404(db, tenant_id=str(tid), tool_name=tool_name)
    try:
        result = check_cli_installed(tool_name=row.name, config=_config(row))
    except CliHostError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(exc), "code": exc.code},
        ) from exc
    logger.info(
        "cli_host_check tool=%s installed=%s path=%s",
        result.tool_name,
        result.installed,
        result.resolved_path,
    )
    return CliHostCheckResponse(
        tool_name=result.tool_name,
        command=result.command,
        installed=result.installed,
        resolved_path=result.resolved_path,
        platform=result.platform,
    )


@router.post("/{tool_name}/install", response_model=CliHostInstallResponse)
def install_cli_host_tool(
    tool_name: str,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CliHostInstallResponse:
    """Attempt to install a registered CLI tool on the host OS (admin control plane)."""
    if not settings.cli_host_install_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CLI host install is disabled (CLI_HOST_INSTALL_ENABLED=false)",
        )
    tid = _require_client_uuid(principal)
    row = _cli_row_or_404(db, tenant_id=str(tid), tool_name=tool_name)
    try:
        result = install_cli_tool(
            tool_name=row.name,
            config=_config(row),
            timeout_seconds=settings.cli_host_install_timeout_seconds,
            max_output_bytes=settings.cli_tools_max_output_bytes,
        )
    except CliHostError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(exc), "code": exc.code},
        ) from exc
    return CliHostInstallResponse(
        tool_name=result.tool_name,
        command=result.command,
        ok=result.ok,
        installed=result.installed,
        install_cmd=result.install_cmd,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        resolved_path=result.resolved_path,
        platform=result.platform,
        error=result.error,
    )


@router.patch("/{tool_name}/install-spec", response_model=CliHostToolRow)
def update_cli_host_install_spec(
    tool_name: str,
    body: CliHostInstallSpecUpdate,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> CliHostToolRow:
    """Set or clear package / install command on a CLI tool (merged into config)."""
    if body.package is None and body.install is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provide package and/or install",
        )
    tid = _require_client_uuid(principal)
    row = _cli_row_or_404(db, tenant_id=str(tid), tool_name=tool_name)
    merged = _merge_install_spec(
        _config(row),
        package=body.package,
        install=body.install,
    )
    updated = update_tool_registry(
        db,
        tenant_id=str(tid),
        name=row.name,
        config=merged,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tool not found")
    db.commit()
    cfg = _config(updated)
    command: str | None = None
    package: str | None = None
    try:
        command = command_from_config(cfg)
        if isinstance(cfg, dict):
            try:
                package = package_from_config(cfg, command=command or "")
            except CliHostError:
                package = str(cfg.get("package") or "").strip() or None
    except CliHostError:
        command = None
    logger.info(
        "cli_host_install_spec_updated tool=%s has_spec=%s",
        updated.name,
        has_install_spec(cfg),
    )
    return CliHostToolRow(
        id=str(updated.id),
        name=updated.name,
        description=updated.description,
        command=command,
        package=package,
        install=_install_spec_text(cfg),
        has_install_spec=has_install_spec(cfg),
        created_at=str(updated.created_at) if updated.created_at else None,
    )
